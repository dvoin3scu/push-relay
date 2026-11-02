import base64
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from push_relay.app import Application, Request
from push_relay.config import Settings
from tests.helpers import FakeServer, payload

KEY = "0123456789abcdef0123456789abcdef"


def decrypt(body: dict) -> dict:
    data = base64.b64decode(body["ciphertext"])
    return json.loads(AESGCM(KEY.encode()).decrypt(body["iv"].encode(), data, None))


class AppTest(unittest.TestCase):
    def setUp(self):
        self.bark = FakeServer()
        self.ntfy = FakeServer()
        self.config = tempfile.TemporaryDirectory()
        self.env = {
            "PUSH_TOKEN": "secret", "PUSH_CONFIG_DIR": self.config.name, "PUSH_RETRY_DELAY": "0",
            "BARK_SERVER": self.bark.url, "BARK_DEVICE_KEYS": "dev1, dev2", "BARK_KEY": KEY,
            "NTFY_SERVER": self.ntfy.url, "NTFY_TOKEN": "tk",
            "SEERR_URL": "https://requests.example/",
        }

    def tearDown(self):
        self.bark.close()
        self.ntfy.close()
        self.config.cleanup()

    def app(self, **env) -> Application:
        return Application(Settings.from_env({**self.env, **env}))

    def post(self, app, path, body, query=None, headers=None):
        query = {"token": "secret", **(query or {})}
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        return app.handle(Request("POST", path, query, headers or {}, data))

    def test_health(self):
        r = self.app().handle(Request("GET", "/health"))
        self.assertEqual((r.status, r.payload["backends"]), (200, ["bark", "ntfy"]))
        r = self.app(BARK_DEVICE_KEYS="", NTFY_SERVER="").handle(Request("GET", "/health"))
        self.assertEqual(r.status, 503)
        r = self.app(BARK_KEY="short").handle(Request("GET", "/health"))
        self.assertEqual(r.status, 503)

    def test_auth(self):
        app = self.app()
        self.assertEqual(self.post(app, "/hook/radarr", {}, query={"token": "nope"}).status, 401)
        r = app.handle(Request("POST", "/hook/radarr", {}, {"authorization": "Bearer secret"},
                               json.dumps({"eventType": "Test"}).encode()))
        self.assertEqual(r.status, 200)

    def test_radarr_grab_end_to_end(self):
        r = self.post(self.app(), "/hook/radarr", payload("radarr-grab"), {"instance": "radarr-4k"})
        self.assertEqual((r.status, r.payload["sent"]), (200, ["bark", "ntfy"]))

        self.assertEqual(len(self.bark.requests), 2)  # one per device, each with its own IV
        (path, _, first), (_, _, second) = self.bark.requests
        self.assertEqual((path, first["device_key"], second["device_key"]), ("/push", "dev1", "dev2"))
        self.assertNotEqual(first["iv"], second["iv"])
        message = decrypt(first)
        self.assertEqual(message["title"], "🎬 radarr-4k · Drive (2011)")
        self.assertEqual(message["subtitle"], "Grabbed")
        self.assertEqual(message["body"], "WEBDL-2160p · FLUX · 9.0 GB\nNZBgeek (Prowlarr) · qBittorrent")
        self.assertEqual((message["level"], message["group"], message["url"]), ("passive", "arrs", "https://www.themoviedb.org/movie/64690"))
        self.assertNotIn("volume", message)

        _, headers, ntfy = self.ntfy.requests[0]
        self.assertEqual(headers["Authorization"], "Bearer tk")
        self.assertEqual(ntfy["topic"], "arrs")
        self.assertEqual(ntfy["title"], "radarr-4k · Drive (2011)")
        self.assertEqual(ntfy["message"], "Movie grabbed!\n\nWEBDL-2160p · FLUX · 9.0 GB\nNZBgeek (Prowlarr) · qBittorrent")
        self.assertEqual((ntfy["priority"], ntfy["tags"]), (2, ["clapper"]))
        self.assertEqual(ntfy["actions"][1]["url"], "https://requests.example/movie/64690")

    def test_groups(self):
        app = self.app()
        self.post(app, "/hook/radarr", payload("health-error"), {"instance": "radarr-hd"})
        self.assertEqual(decrypt(self.bark.requests[-1][2])["group"], "system")
        self.assertEqual(self.ntfy.requests[-1][2]["topic"], "system")
        self.post(app, "/hook/seerr", payload("seerr-pending"), {"group": "Kids Requests"})
        self.assertEqual(decrypt(self.bark.requests[-1][2])["group"], "Kids Requests")
        self.assertEqual(self.ntfy.requests[-1][2]["topic"], "kids-requests")
        self.post(app, "/notify/speedtest", {"body": "x"})
        self.assertEqual(decrypt(self.bark.requests[-1][2])["group"], "network")
        self.post(app, "/notify/unknown", {"body": "x", "urls": "bark://active?group=from-payload"})
        self.assertEqual(decrypt(self.bark.requests[-1][2])["group"], "from-payload")
        self.post(app, "/notify/unknown", {"body": "x", "urls": "bark://active?group=from-payload"}, {"group": "from-url"})
        self.assertEqual(decrypt(self.bark.requests[-1][2])["group"], "from-url")
        self.post(app, "/notify/unknown", {"body": "x"})
        self.assertEqual(decrypt(self.bark.requests[-1][2])["group"], "system")

    def test_url_customisation_wins_over_apps_yaml(self):
        query = {"instance": "radarr-4k", "emoji": "🎥", "icon": "https://x/i.png", "tap": "https://x",
                 "name": "Movies", "tag": "movie_camera", "level": "critical", "group": "films"}
        self.post(self.app(), "/hook/radarr", payload("radarr-grab"), query)
        message = decrypt(self.bark.requests[0][2])
        self.assertEqual(message["title"], "🎥 Movies · Drive (2011)")
        self.assertEqual((message["icon"], message["url"], message["level"], message["group"]),
                         ("https://x/i.png", "https://x", "critical", "films"))
        ntfy = self.ntfy.requests[0][2]
        self.assertEqual((ntfy["tags"], ntfy["priority"], ntfy["topic"]), (["movie_camera"], 5, "films"))

    def test_whisparr_has_no_image(self):
        self.post(self.app(), "/hook/whisparr", payload("radarr-grab"), {"instance": "whisparr"})
        self.assertNotIn("image", decrypt(self.bark.requests[0][2]))
        self.assertNotIn("attach", self.ntfy.requests[0][2])

    def test_whisparr_taps_to_stashdb_unless_url_says_otherwise(self):
        scene = payload("radarr-grab")
        scene["movie"]["stashId"] = "abc-123"
        self.post(self.app(), "/hook/whisparr", scene, {"instance": "whisparr"})
        self.assertEqual(decrypt(self.bark.requests[-1][2])["url"], "https://stashdb.org/scenes/abc-123")
        self.post(self.app(), "/hook/whisparr", scene, {"instance": "whisparr", "tap": "https://x"})
        self.assertEqual(decrypt(self.bark.requests[-1][2])["url"], "https://x")
        self.post(self.app(), "/hook/whisparr", payload("radarr-grab"), {"instance": "whisparr"})
        self.assertNotIn("url", decrypt(self.bark.requests[-1][2]))

    def test_health_error_is_critical(self):
        self.post(self.app(BARK_CRITICAL_VOLUME="6"), "/hook/radarr", payload("health-error"), {"instance": "radarr-hd"})
        message = decrypt(self.bark.requests[0][2])
        self.assertEqual(message["title"], "🚨 radarr-hd · Download client")
        self.assertEqual((message["level"], message["volume"]), ("critical", 6))
        self.assertEqual(self.ntfy.requests[0][2]["priority"], 5)

    def test_overrides_from_config_dir(self):
        rules = Path(self.config.name, "rules")
        rules.mkdir()
        (rules / "severity.yaml").write_text("events:\n  radarr.radarr-4k.grab: high\n")
        (rules / "apps.yaml").write_text("radarr:\n  instances:\n    radarr-4k: {name: Radarr 4K, group: movies}\n")
        tpl = Path(self.config.name, "templates", "bark")
        tpl.mkdir(parents=True)
        (tpl / "radarr.media.json").write_text('{"title": "{{instance}}", "body": "{{headline}}", "level": "{{level}}", "group": "{{group}}"}')
        self.post(self.app(), "/hook/radarr", payload("radarr-grab"), {"instance": "radarr-4k"})
        message = decrypt(self.bark.requests[0][2])
        self.assertEqual(message, {"title": "Radarr 4K", "body": "Drive (2011)", "level": "timeSensitive", "group": "movies"})

    def test_backend_failure_and_retry(self):
        self.bark.statuses = [503, 503, 400, 400]  # dev1: retried then fails; dev2: 400 is not retried
        r = self.post(self.app(NTFY_SERVER=""), "/hook/sonarr", {"eventType": "Test"})
        self.assertEqual(r.status, 502)
        self.assertEqual(len(self.bark.requests), 3)

    def test_ignored_and_bad_payloads(self):
        app = self.app()
        self.assertEqual(self.post(app, "/hook/radarr", {"eventType": "Nope"}).payload, {"status": "ignored"})
        self.assertEqual(self.post(app, "/hook/radarr", b"not json").status, 400)
        r = self.post(app, "/hook/unknown", {})
        self.assertEqual((r.status, r.payload["status"]), (200, "sent"))
        self.assertEqual(decrypt(self.bark.requests[-1][2])["title"], "unknown")

    def test_generic_adapter(self):
        app = self.app(NTFY_SERVER="")
        readarr = {"eventType": "Download", "instanceName": "Readarr",
                   "author": {"name": "Brandon Sanderson"}, "book": {"title": "The Way of Kings",
                   "images": [{"coverType": "cover", "remoteUrl": "https://example.org/wok.jpg"}]}}
        self.post(app, "/hook/readarr", readarr, {"instance": "readarr"})
        m = decrypt(self.bark.requests[-1][2])
        self.assertEqual((m["title"], m["subtitle"], m["image"], m["group"]),
                         ("readarr · Brandon Sanderson – The Way of Kings", "Download", "https://example.org/wok.jpg", "system"))
        self.post(app, "/hook/readarr", {"eventType": "Health", "level": "warning", "type": "IndexerStatusCheck",
                                         "message": "Indexers unavailable"}, {"instance": "readarr"})
        m = decrypt(self.bark.requests[-1][2])
        self.assertEqual((m["title"], m["body"], m["level"]), ("🚧 readarr · Indexer status", "Indexers unavailable", "timeSensitive"))
        self.post(app, "/hook/jellyfin", {"NotificationType": "ItemAdded", "ServerName": "jf", "Year": 2025})
        m = decrypt(self.bark.requests[-1][2])
        self.assertEqual((m["title"], m["body"]), ("jellyfin", "NotificationType: ItemAdded\nServerName: jf\nYear: 2025"))

    def test_notify_apprise_json_and_form(self):
        app = self.app(NTFY_SERVER="")
        r = self.post(app, "/notify/speedtest", {"urls": "bark://critical", "title": "Speedtest", "body": "Down: 0 Mbps"})
        self.assertEqual((r.status, r.payload), (200, {"success": True}))
        message = decrypt(self.bark.requests[0][2])
        self.assertEqual((message["title"], message["body"], message["level"]), ("🚀 speedtest · Speedtest", "Down: 0 Mbps", "critical"))

        r = self.post(app, "/notify", b"title=Bazarr&body=Subtitle+downloaded&type=info",
                      query={"instance": "bazarr"}, headers={"content-type": "application/x-www-form-urlencoded"})
        message = decrypt(self.bark.requests[-1][2])
        self.assertEqual((message["title"], message["level"]), ("bazarr · Bazarr", "active"))

    def test_notify_markdown_keeps_links_for_bark_and_ntfy(self):
        body = "**Upload** below threshold\n- [View Dashboard](https://speed.example)"
        self.post(self.app(), "/notify/speedtest", {"title": "Speedtest", "body": body, "format": "markdown"})
        message = decrypt(self.bark.requests[0][2])
        self.assertEqual((message["markdown"], message["body"]), (body, "Upload below threshold\n- View Dashboard"))
        ntfy = self.ntfy.requests[0][2]
        self.assertEqual((ntfy["message"], ntfy["markdown"]), (body, True))
        self.post(self.app(), "/notify/speedtest", {"title": "Speedtest", "body": "plain"})
        self.assertNotIn("markdown", decrypt(self.bark.requests[-1][2]))
        self.assertNotIn("markdown", self.ntfy.requests[-1][2])

    def test_seerr_issues_tap_to_the_issue_in_seerr(self):
        issue = {"notification_type": "ISSUE_CREATED", "subject": "Dune (2021)", "message": "No audio",
                 "media": {"media_type": "movie", "tmdbId": "438631"},
                 "issue": {"issue_id": "7", "issue_type": "AUDIO", "reportedBy_username": "alice"}}
        self.post(self.app(), "/hook/seerr", issue)
        self.assertEqual(decrypt(self.bark.requests[-1][2])["url"], "https://requests.example/issues/7")
        self.post(self.app(), "/hook/seerr", payload("seerr-pending"))
        self.assertEqual(decrypt(self.bark.requests[-1][2])["url"], "https://requests.example/movie/693134")
        self.post(self.app(SEERR_URL=""), "/hook/seerr", issue)
        self.assertNotIn("url", decrypt(self.bark.requests[-1][2]))

    def test_media_taps_to_public_pages_and_health_has_none(self):
        self.post(self.app(), "/hook/sonarr", payload("sonarr-import-complete"), {"instance": "sonarr-hd"})
        self.assertEqual(decrypt(self.bark.requests[-1][2])["url"], "https://www.themoviedb.org/tv/95396")
        album = payload("lidarr-grab")
        album["albums"][0]["mbId"] = "b1392450-e666-3926-a536-22c65f834433"
        album["artist"]["mbId"] = "a74b1b7f-71a5-4011-9441-d0b5e4122711"
        self.post(self.app(), "/hook/lidarr", album, {"instance": "lidarr"})
        self.assertEqual(decrypt(self.bark.requests[-1][2])["url"],
                         "https://musicbrainz.org/release-group/b1392450-e666-3926-a536-22c65f834433")
        album["albums"] = []
        self.post(self.app(), "/hook/lidarr", album, {"instance": "lidarr"})
        self.assertEqual(decrypt(self.bark.requests[-1][2])["url"],
                         "https://musicbrainz.org/artist/a74b1b7f-71a5-4011-9441-d0b5e4122711")
        self.post(self.app(), "/hook/radarr", payload("health-error"), {"instance": "radarr-hd"})
        self.assertTrue(decrypt(self.bark.requests[-1][2])["url"].startswith("https://wiki.servarr.com/"))
        self.post(self.app(), "/hook/radarr", payload("update"), {"instance": "radarr-hd"})
        self.assertNotIn("url", decrypt(self.bark.requests[-1][2]))
        self.post(self.app(), "/hook/decypharr", payload("decypharr-repair-failed"), {"instance": "decypharr"})
        self.assertNotIn("url", decrypt(self.bark.requests[-1][2]))

    def test_dispatcharr_form_without_template(self):
        r = self.post(self.app(), "/hook/dispatcharr", b"channel_name=News+1&stream_name=News+HD&provider_name=IPTV+A",
                      {"instance": "iptv"}, headers={"content-type": "application/x-www-form-urlencoded"})
        self.assertEqual(r.status, 200)
        m = decrypt(self.bark.requests[-1][2])
        self.assertEqual((m["title"], m["subtitle"], m["body"], m["group"], m["level"]),
                         ("▶️ iptv · News 1", "Channel started", "News HD · IPTV A", "iptv", "passive"))
        self.post(self.app(), "/hook/dispatcharr", {"event": "login_failed", "user": "admin", "reason": "invalid credentials",
                                                     "client_ip": "1.2.3.4"}, {"instance": "iptv"})
        m = decrypt(self.bark.requests[-1][2])
        self.assertEqual((m["title"], m["group"], m["level"]), ("🔐 iptv · admin", "system", "timeSensitive"))

    def test_notify_always_200(self):
        self.bark.statuses = [500, 500, 500, 500]
        r = self.post(self.app(NTFY_SERVER=""), "/notify", b"{broken")
        self.assertEqual((r.status, r.payload), (200, {"success": False}))


if __name__ == "__main__":
    unittest.main()
