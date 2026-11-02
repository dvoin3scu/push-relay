# push-relay

A small webhook relay that turns notifications from the *arr apps, Seerr, Decypharr and any
Apprise-speaking app into **end-to-end encrypted [Bark](https://bark.day.app) pushes** (with
posters, icons, groups and tap actions) and/or **[ntfy](https://ntfy.sh)** messages.

```
Radarr / Sonarr / Lidarr / Whisparr / Prowlarr ─┐
Seerr ──────────────────────────────────────────┤  POST /hook/<source>   ┌─► Bark (AES-GCM)
Decypharr ──────────────────────────────────────┤ ─────────────────────► │
Apprise / custom JSON (Speedtest, …) ───────────┘  POST /notify[/<key>]  └─► ntfy
```

## How it works

```
payload ─► source adapter ─► Event ─► rules (severity, app profile) ─► view ─► template per backend ─► notifier
```

| Module | Responsibility |
|---|---|
| `push_relay/sources/` | One adapter per sender. Reads the payload, builds a normalised `Event`. No presentation. |
| `push_relay/rules.py` | Severity per event (`severity.yaml`) and per-app presentation (`apps.yaml`). |
| `push_relay/view.py` | Turns an `Event` + app profile into the flat view the templates use. |
| `push_relay/templates.py` | Logic-less JSON templates (`{{var}}`, `{{#var}}…{{/var}}`, `{{^var}}…{{/var}}`). |
| `push_relay/notifiers/` | One notifier per backend: adds backend fields (Bark level, ntfy priority), renders, delivers. |
| `push_relay/dispatcher.py` | Runs one event through every enabled notifier. |
| `push_relay/app.py` | Routing, auth and endpoint logic (no sockets, easy to test). |
| `push_relay/server.py` | Standard-library HTTP server. |

## Configuration (environment)

| Variable | Default | |
|---|---|---|
| `PUSH_TOKEN` | — | Shared secret. Send it as `?token=`, `Authorization: Bearer` or `X-Push-Token`. Unset = no auth (logged as a warning). `/health` is always open. |
| `PUSH_PORT` | `8092` | |
| `PUSH_CONFIG_DIR` | `/config` | Optional overrides (see below). |
| `SEERR_URL` | — | Base URL for "Seerr" links (e.g. `https://requests.example.com`). |
| `BARK_DEVICE_KEYS` | — | Comma-separated device keys. **Enables Bark.** |
| `BARK_KEY` | — | Encryption key from the Bark app (AES-GCM, 16/24/32 characters). |
| `BARK_SERVER` | `https://api.day.app` | Or a self-hosted bark-server. |
| `BARK_USER` / `BARK_PASSWORD` | — | Basic auth for a self-hosted bark-server. |
| `BARK_CRITICAL_VOLUME` | `4` | Volume (0–10) of critical alerts. |
| `NTFY_SERVER` | — | e.g. `https://ntfy.sh`. **Enables ntfy.** The topic is the event's group (see below). |
| `NTFY_TOKEN` | — | Access token (optional). |
| `PUSH_TIMEOUT` / `PUSH_RETRY_DELAY` | `10` / `5` | Seconds. One retry on network errors, 429 and 5xx; none on other 4xx. |
| `LOG_LEVEL` | `INFO` | |

With neither backend configured, or an invalid `BARK_KEY`, `/health` answers 503 (container unhealthy).

## Endpoints

| Endpoint | |
|---|---|
| `GET /health` | `200 {"status":"ok","backends":[…]}` or `503` with the problems. |
| `POST /hook/<source>?instance=<name>` | `radarr`, `sonarr`, `lidarr`, `whisparr`, `prowlarr`, `seerr`, `decypharr`. `200` when at least one backend accepted it (or the event is ignored), `502` when all failed, so the app's **Test** button shows real failures. |
| `POST /notify[/<key>]` | Apprise API emulation (`{urls, title, body, type, format, tag}`, JSON or form). `<key>` (or `?instance=`) is the instance name. The level comes from the URL (`bark://timeSensitive`, `bark://critical`, `ntfy://high`, `barks://…?level=…`) or the tag, else from the type. Always `200`. |

`instance` is the display name (e.g. `radarr-4k`). Without it: the payload's `instanceName`, then the source name.

### Customising from the URL

Both endpoints accept query parameters that win over `apps.yaml` and the severity rules:

| Parameter | Effect |
|---|---|
| `group` | Bark group and ntfy topic |
| `level` | `passive` / `active` / `timeSensitive` / `critical` (or `low` / `normal` / `high` / `urgent`) |
| `name` | display name in the title |
| `emoji` | title emoji (events with their own, like health and test, keep theirs) |
| `icon` | Bark icon URL |
| `tap` | URL opened on tap |
| `tag` | ntfy tag |

Example: `http://push:8092/hook/radarr?instance=radarr-4k&group=movies&level=timeSensitive&token=…`

## Groups

One group per event: the **Bark group** and the **ntfy topic** (lower-cased, `[a-z0-9-]`).
Order: `?group=`, then (on `/notify`) a group from the Apprise side, then `apps.yaml` (`groups[kind]`, then `group`).

| Default group | Events |
|---|---|
| `arrs` | Radarr, Sonarr, Lidarr, Whisparr, Prowlarr media and test events |
| `system` | Health, health restored and update events from any *arr; anything without a group |
| `requests` | Seerr |
| `downloads` | Decypharr |
| `network` | Speedtest Tracker |

On `/notify` the group can also come from the Apprise side: a `group=` parameter on the notification URL
(`bark://timeSensitive?group=network`) or a `group` field in the payload (`json://…?-group=media`).

On the public ntfy.sh, topics are shared by everyone: reserve them or use your own ntfy server.

## Severity

| Severity | Bark level | ntfy priority |
|---|---|---|
| `low` | passive | 2 |
| `normal` | active | 3 |
| `high` | timeSensitive | 4 |
| `urgent` | critical (+ volume) | 5 |

Defaults are in [`push_relay/defaults/rules/severity.yaml`](push_relay/defaults/rules/severity.yaml).

## Setting up the apps

Replace `push:8092` with the LAN address (e.g. `192.168.1.10:8092`) for apps that cannot resolve the
container name (for example behind a VPN container).

**Radarr / Sonarr / Lidarr / Whisparr / Prowlarr** — Settings → Connect → + → **Webhook**
- URL `http://push:8092/hook/radarr?instance=radarr-4k&token=…`, Method `POST`.
- Pick the triggers you want. Sonarr: use **On Import Complete** (one notification per download) instead of On File Import.

**Seerr** — Settings → Notifications → **Webhook**: URL `http://push:8092/hook/seerr?token=…`, keep the default JSON payload.

**Decypharr** — `config.json`:
```json
"notifications": { "enabled": true, "callback_url": "http://push:8092/hook/decypharr?token=…", "events": ["download_failed", "repair_failed"] }
```

**Apprise-only apps (Speedtest Tracker, …)** — point the Apprise API URL at
`http://push:8092/notify/<name>?token=…` and use a notification URL that names the level, e.g. `bark://timeSensitive`.

## Other apps

- **Speaks Apprise, or lets you write the webhook JSON** (Jellyfin webhook plugin, Home Assistant, scripts, …):
  send `{"title": "…", "body": "…", "type": "info"}` to `/notify/<name>`. It uses the `generic` template
  (`<name> · <title>` + body, no emoji) and is customised with `?emoji=`, `?icon=`, `?group=`, `?level=`, … or an
  `apps.yaml` entry under `notify.instances`. No code needed.
- **Only sends its own fixed format** (e.g. a new *arr-style webhook): add one adapter in `push_relay/sources/`
  that turns the payload into an `Event` and register it. It then uses the existing `media` / `health` /
  `generic` templates; a `<source>.<kind>.json` template is only needed for a different look.

Templates are per kind of event, not per app, so a new app never needs its own template.

## Overrides (`/config`)

Nothing is required in `/config`. To customise, add only what changes:

```
/config/rules/severity.yaml          deep-merged over the defaults
/config/rules/apps.yaml              deep-merged over the defaults
/config/templates/bark/<kind>.json            replaces a default template
/config/templates/bark/<source>.<kind>.json   for one source only
```

Kinds: `media`, `health`, `generic`. Examples:

```yaml
# /config/rules/severity.yaml — the lookup order is <source>.<instance>.<action>, <source>.<action>, <action>
events:
  radarr.radarr-4k.grab: normal
  seerr.request_available: high
```

```yaml
# /config/rules/apps.yaml
radarr:
  instances:
    radarr-4k: {group: movies-4k, groups: {health: health-4k}}
```

Template view fields: `instance emoji label headline summary body image url icon group tag links source kind action severity`,
plus `level volume` (Bark) and `priority tags actions` (ntfy). A value that is exactly `"{{name}}"` is
replaced by the raw value (list/number); empty fields are dropped.

## Development

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -t .
PUSH_PORT=8092 BARK_DEVICE_KEYS=… BARK_KEY=… python -m push_relay
```

Images: `ghcr.io/dvoin3scu/push-relay` (`latest` from `main`, `X.Y.Z`/`X.Y` from `vX.Y.Z` tags, `sha-…`), built by
`.github/workflows/docker.yml` for amd64 and arm64.
