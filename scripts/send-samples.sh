#!/usr/bin/env bash
# Sends one sample of every notification variation to a running push-relay, so you can see them on the phone.
# Usage:
#   PUSH_URL=http://192.168.1.10:8092 PUSH_TOKEN=… scripts/send-samples.sh --list
#   PUSH_URL=… PUSH_TOKEN=… scripts/send-samples.sh all              # every sample, 3 s apart
#   PUSH_URL=… PUSH_TOKEN=… scripts/send-samples.sh radarr-grab health-error
# Note: health-error is a critical alert (sound, even in silent mode).
set -euo pipefail
cd "$(dirname "$0")/.."
URL="${PUSH_URL:-http://localhost:8092}"
TOKEN="${PUSH_TOKEN:-}"
P=tests/payloads

# name | path?query (without token) | payload (@file or inline JSON) | what you should see
SAMPLES=(
  "radarr-grab|/hook/radarr?instance=radarr-4k|@$P/radarr-grab.json|🎬 radarr-4k · Drive (2011) / Grabbed, poster, passive, group arrs"
  "radarr-upgrade|/hook/radarr?instance=radarr-4k|@$P/radarr-download.json|🎬 radarr-4k · Drive (2011) / Upgraded, no size (only grabs show it), no poster in this sample, active, arrs"
  "sonarr-import|/hook/sonarr?instance=sonarr-hd|@$P/sonarr-import-complete.json|📺 sonarr-hd · Severance – S02E01–E03 / Imported, poster, active, arrs"
  "lidarr-grab|/hook/lidarr?instance=lidarr|@$P/lidarr-grab.json|🎵 lidarr · Radiohead – OK Computer (1997) / Grabbed, passive, arrs (cover is a placeholder URL)"
  "whisparr-grab|/hook/whisparr?instance=whisparr|@$P/radarr-grab.json|🔞 whisparr · Drive (2011) / Grabbed, NO image, passive, arrs"
  "whisparr-stashdb|/hook/whisparr?instance=whisparr|{\"eventType\":\"Download\",\"movie\":{\"title\":\"Sample scene\",\"year\":2024,\"stashId\":\"00000000-0000-0000-0000-000000000000\"},\"movieFile\":{\"relativePath\":\"Sample.mp4\",\"quality\":\"WEBDL-1080p\"}}|🔞 whisparr · Sample scene (2024) / Imported; tap opens stashdb.org/scenes/0000… (placeholder id, so StashDB shows not found)"
  "manual-import|/hook/radarr?instance=radarr-hd|{\"eventType\":\"ManualInteractionRequired\",\"movie\":{\"title\":\"Heat\",\"year\":1995,\"tmdbId\":949},\"downloadInfo\":{\"quality\":\"Bluray-1080p\",\"size\":12884901888},\"downloadClient\":\"SABnzbd\",\"downloadStatus\":\"warning\",\"downloadStatusMessages\":[{\"title\":\"Heat\",\"messages\":[\"Unable to determine if file is a sample\"]}]}|🎬 radarr-hd · Heat (1995) / Manual import needed, timeSensitive, arrs"
  "arr-test|/hook/sonarr?instance=sonarr-4k|{\"eventType\":\"Test\"}|🧪 sonarr-4k / Test, body 'Test notification from sonarr-4k', active, arrs"
  "health-warning|/hook/radarr?instance=radarr-hd|{\"eventType\":\"Health\",\"level\":\"warning\",\"type\":\"IndexerStatusCheck\",\"message\":\"Indexers unavailable due to failures: NZBgeek\"}|🚧 radarr-hd · Indexer status / Health warning, timeSensitive, group system"
  "health-error|/hook/radarr?instance=radarr-hd|@$P/health-error.json|🚨 radarr-hd · Download client / Health error, CRITICAL (volume), system"
  "health-restored|/hook/radarr?instance=radarr-hd|@$P/health-restored.json|✅ radarr-hd · Indexer status / 'Resolved: …', passive, system"
  "update|/hook/prowlarr?instance=prowlarr|@$P/update.json|⬆️ prowlarr · Updated / 1.30.0 → 1.31.2, passive, system"
  "seerr-request|/hook/seerr?instance=seerr|@$P/seerr-pending.json|🍿 seerr · Dune: Part Two (2024) / Pending approval, 'Requested by alice', active, group requests"
  "decypharr-failed|/hook/decypharr?instance=decypharr|@$P/decypharr-repair-failed.json|❌ decypharr · Some.Show.S01E01 / Repair failed, timeSensitive, group downloads"
  "speedtest|/notify/speedtest|{\"urls\":\"bark://timeSensitive\",\"title\":\"Speedtest completed\",\"body\":\"**Download:** 940 Mbps\\n**Upload:** 480 Mbps\\n**Ping:** 4 ms\",\"type\":\"warning\",\"format\":\"markdown\"}|🚀 speedtest · Speedtest completed / 3 lines without markdown, timeSensitive, group network"
  "notify-generic|/notify/backup|{\"title\":\"Backup finished\",\"body\":\"appdata: 42 containers, 3.1 GB\",\"type\":\"success\"}|backup · Backup finished (no emoji), active, group system"
  "hook-generic|/hook/homeassistant?group=casa&level=timeSensitive|{\"title\":\"Porta da garagem\",\"message\":\"Aberta há 10 minutos\",\"event\":\"alert\"}|homeassistant · Porta da garagem / Alert, timeSensitive, group casa"
  "hook-unknown|/hook/jellyfin|{\"NotificationType\":\"ItemAdded\",\"ServerName\":\"jf\",\"Year\":2025}|jellyfin / body lists the first fields, active, system"
  "url-custom|/hook/radarr?instance=radarr-4k&name=Movies&emoji=%F0%9F%8E%A5&group=films&level=active&tap=https%3A%2F%2Fwww.themoviedb.org|@$P/radarr-grab.json|🎥 Movies · Drive (2011), active, group films, tap opens TMDB"
)

list() { for s in "${SAMPLES[@]}"; do IFS='|' read -r name _ _ expect <<<"$s"; printf '%-17s %s\n' "$name" "$expect"; done; }

send() {
  local name path data expect sep
  IFS='|' read -r name path data expect <<<"$1"
  sep='?'; [[ "$path" == *\?* ]] && sep='&'
  printf '%-17s → %s\n' "$name" "$expect"
  # --data-binary reads "@file" as a file and anything else as the JSON itself
  curl -sS -X POST -H 'Content-Type: application/json' --data-binary "$data" "${URL}${path}${sep}token=${TOKEN}"
  echo
}

case "${1:---list}" in
  --list|-l) list ;;
  all) for s in "${SAMPLES[@]}"; do send "$s"; sleep 3; done ;;
  *) for want in "$@"; do
       found=""
       for s in "${SAMPLES[@]}"; do [[ "${s%%|*}" == "$want" ]] && { send "$s"; found=1; }; done
       [ -n "$found" ] || echo "unknown sample: $want (see --list)" >&2
     done ;;
esac
