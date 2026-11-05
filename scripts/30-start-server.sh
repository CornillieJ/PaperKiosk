#!/usr/bin/env bash
# Step 3: build and start the PaperKiosk server (docker compose up -d --build), wait until it answers,
# then show the two addresses you need: the settings page, and the one-time kiosk link for screens.
source "$(dirname "$0")/lib.sh"

title "Start the server" "docker compose up -d --build"
env_init; ensure_dirs
secret_has kiosk_key && secret_has admin_password || fail "Run ./scripts/10-configure.sh first (keys and password)."
secret_has ha_token || warn "No Home Assistant token yet: the kiosk shows an error until ./scripts/20-home-assistant.sh ran."

spin "Building and starting" compose up -d --build --remove-orphans
PORT=$(env_get PAPERKIOSK_PORT); PORT=${PORT:-8100}
for _ in $(seq 1 30); do
  curl -fs -m 3 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -fs -m 3 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 || {
  compose logs --tail 30 paperkiosk >&2; fail "PaperKiosk doesn't answer on port $PORT (logs above)."; }
ok "PaperKiosk is running"

URL=$(env_get PAPERKIOSK_URL)
explain <<EOF
**Settings page** (on your PC or phone): $URL/config
log in with the password you chose.

**Kiosk link** for a screen (opened once, then the screen stays paired):
\`$(kiosk_link)\`

Keep that link to yourself: whoever has it can use the kiosk. Other screens than a Kindle (an old tablet,
a Kobo browser, ...): open the link in their browser and add it to the home screen.
EOF
