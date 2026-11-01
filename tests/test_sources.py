import unittest

from push_relay.sources import NOTIFY, SOURCES, Context, PayloadError
from tests.helpers import payload

CTX = Context(instance="radarr-4k", seerr_url="https://requests.example")


class ArrTest(unittest.TestCase):
    def test_radarr_grab(self):
        e = SOURCES["radarr"].parse(payload("radarr-grab"), CTX)
        self.assertEqual((e.kind, e.action, e.instance), ("media", "grab", "radarr-4k"))
        self.assertEqual(e.headline, "Drive (2011)")
        self.assertEqual(e.summary, "Movie grabbed!")
        self.assertEqual(e.details, ["WEBDL-2160p · FLUX · 9.0 GB", "NZBgeek (Prowlarr) · qBittorrent"])
        self.assertTrue(e.image.startswith("https://image.tmdb.org/"))
        self.assertEqual([l.label for l in e.links], ["TMDB", "Seerr"])
        self.assertEqual(e.links[1].url, "https://requests.example/movie/64690")

    def test_radarr_upgrade(self):
        e = SOURCES["radarr"].parse(payload("radarr-download"), CTX)
        self.assertEqual((e.action, e.label), ("upgrade", "Upgraded"))
        self.assertEqual(e.body, "Bluray-2160p · WtFnZb · 13.1 GB\nNZBgeek (Prowlarr) · SABnzbd")

    def test_instance_falls_back_to_payload(self):
        e = SOURCES["radarr"].parse(payload("radarr-grab"), Context(instance=""))
        self.assertEqual(e.instance, "Radarr 4K")

    def test_sonarr_import_complete(self):
        e = SOURCES["sonarr"].parse(payload("sonarr-import-complete"), CTX)
        self.assertEqual(e.headline, "Severance – S02E01–E03")
        self.assertEqual(e.summary, "3 episodes imported successfully!")
        self.assertEqual(e.details[0], "WEBDL-1080p · NTb · 2.8 GB")
        self.assertEqual(e.links[0].url, "https://www.themoviedb.org/tv/95396")

    def test_lidarr_grab(self):
        e = SOURCES["lidarr"].parse(payload("lidarr-grab"), CTX)
        self.assertEqual(e.headline, "Radiohead – OK Computer (1997)")
        self.assertEqual(e.image, "https://example.org/okc.jpg")

    def test_whisparr_has_no_tmdb_links(self):
        e = SOURCES["whisparr"].parse(payload("radarr-grab"), CTX)
        self.assertEqual((e.summary, e.links), ("Scene grabbed!", []))

    def test_health(self):
        e = SOURCES["radarr"].parse(payload("health-error"), CTX)
        self.assertEqual((e.kind, e.action, e.emoji, e.headline), ("health", "health_error", "🚨", "Download client"))
        e = SOURCES["sonarr"].parse(payload("health-restored"), CTX)
        self.assertEqual(e.body, "Resolved: Indexers unavailable due to failures: NZBgeek")
        e = SOURCES["prowlarr"].parse(payload("update"), CTX)
        self.assertEqual((e.action, e.body), ("update", "1.30.0 → 1.31.2"))

    def test_test_event_and_ignored_event(self):
        e = SOURCES["sonarr"].parse({"eventType": "Test"}, CTX)
        self.assertEqual((e.action, e.summary), ("test", "Test notification from radarr-4k"))
        self.assertIsNone(SOURCES["sonarr"].parse({"eventType": "SomethingNew"}, CTX))
        with self.assertRaises(PayloadError):
            SOURCES["sonarr"].parse({}, CTX)


class OtherSourcesTest(unittest.TestCase):
    def test_seerr(self):
        e = SOURCES["seerr"].parse(payload("seerr-pending"), Context(instance="", seerr_url="https://r"))
        self.assertEqual((e.action, e.label, e.headline, e.instance), ("request_pending", "Pending approval", "Dune: Part Two (2024)", "seerr"))
        self.assertEqual(e.details, ["Requested by alice"])
        self.assertEqual(e.links[1].url, "https://r/movie/693134")

    def test_decypharr(self):
        e = SOURCES["decypharr"].parse(payload("decypharr-repair-failed"), Context(instance=""))
        self.assertEqual((e.action, e.label, e.headline, e.emoji), ("repair_failed", "Repair failed", "Some.Show.S01E01", "❌"))
        self.assertEqual(e.details[-1], "shows · debrid")

    def test_notify_levels(self):
        ctx = Context(instance="speedtest")
        e = NOTIFY.parse({"urls": "bark://timeSensitive", "title": "**Speedtest**", "body": "Ping *12 ms*", "format": "markdown"}, ctx)
        self.assertEqual((e.severity, e.headline, e.body, e.instance), ("high", "Speedtest", "Ping 12 ms", "speedtest"))
        self.assertEqual(NOTIFY.parse({"urls": "barks://api.day.app/K?level=critical"}, ctx).severity, "urgent")
        self.assertEqual(NOTIFY.parse({"tag": "passive", "message": "x"}, ctx).severity, "low")
        e = NOTIFY.parse({"body": "x", "type": "failure"}, ctx)
        self.assertEqual((e.severity, e.action, e.emoji), ("", "failure", "❌"))


if __name__ == "__main__":
    unittest.main()
