#!/usr/bin/env bash
# Step 2: connect to Home Assistant: where it runs (HA_URL in .env), a long-lived access token
# (secrets/ha_token) and the room the kiosk hangs in (data/config.json). Tests the connection.
# Unattended: HA_URL, HA_TOKEN, HOME_AREA.
source "$(dirname "$0")/lib.sh"

title "Connect to Home Assistant" "where it runs, an access token, and the kiosk's room"
env_init; ensure_dirs; ensure_image

# --- Where ---------------------------------------------------------------------------------------
IP=$(lan_ip || true)
CURRENT=$(env_get HA_URL)
FOUND=""
if [[ -z "${HA_URL:-}" ]]; then
  FOUND=$(in_container python check_ha.py probe ${CURRENT:+"$CURRENT"} http://host.docker.internal:8123 \
          ${IP:+"http://$IP:8123"} http://homeassistant.local:8123 http://homeassistant:8123 2>/dev/null || true)
  FOUND=${FOUND//$'\r'/}
fi
if [[ -n "$FOUND" ]]; then
  ok "Found Home Assistant at $FOUND"
  [[ "$FOUND" == *host.docker.internal* ]] && info "(that is: on this same machine)"
else
  explain <<'EOF'
Couldn't find Home Assistant by myself. Type its address, the one you open it with in a browser, for example
`http://192.168.1.20:8123`. If it runs on **this** machine use `http://host.docker.internal:8123`.
EOF
fi
ask HA_URL "Home Assistant address" "${FOUND:-${CURRENT:-http://homeassistant.local:8123}}" --required
HA_URL=${HA_URL%/}
[[ "$HA_URL" =~ ^https?://[^/?#\"\'\ ]+$ ]] || fail "Use an address like http://192.168.1.20:8123"
env_set HA_URL "$HA_URL"

# --- Token ---------------------------------------------------------------------------------------
check() {   # sets HA_OK, HA_ERROR, HA_VERSION, HA_LOCATION, HA_USER, HA_ADMIN, HA_ENTITIES, HA_AREAS, HA_AREA_IDS
  HA_OK="" HA_ERROR="no answer from the check"
  local out; out=$(in_container python check_ha.py check --shell 2>/dev/null | tr -d '\r' | grep -E '^HA_[A-Z_]+=') || true
  eval "$out"   # every value is quoted by check_ha.py (shlex.quote)
}

HA_OK=""
if secret_has ha_token && [[ -z "${HA_TOKEN:-}" ]]; then
  check
  if [[ -n "$HA_OK" ]] && ! confirm "There is a working token already. Keep it?" yes; then HA_OK=""; fi
fi
while [[ -z "$HA_OK" ]]; do
  if [[ -z "${HA_TOKEN:-}" ]]; then
    explain <<EOF
PaperKiosk needs a **long-lived access token** to read your devices and switch them.

**Best: give it its own user without admin rights** (then the kiosk can never change Home Assistant itself):

1. Open Home Assistant: $HA_URL
2. *Settings → People → Users → Add user*. Name it \`PaperKiosk\`, any long password,
   turn **Administrator off** and **"Can only log in from the local network" on**.
   (No Users tab? Turn on *Advanced mode* in your profile first: click your name, bottom left.)
3. Log in as that user (a private browser window is easiest), click the name bottom left → **Security** tab.
4. At **Long-lived access tokens** choose **Create token**, name it \`PaperKiosk\`, and copy it.

*Quicker, less safe:* steps 3-4 with your own account.

The token is stored in \`secrets/ha_token\` (only readable by you) and never leaves this server.
EOF
    ask HA_TOKEN "Paste the token" "" --password --required
  fi
  HA_TOKEN=$(tr -d ' \r\n\t' <<<"$HA_TOKEN")
  [[ "$HA_TOKEN" =~ ^[A-Za-z0-9._-]{20,}$ ]] || { warn "That doesn't look like a token (a long text with dots)."; HA_TOKEN=""; continue; }
  printf '%s' "$HA_TOKEN" | secret_set ha_token
  check
  if [[ -z "$HA_OK" ]]; then
    warn "Home Assistant says: $HA_ERROR"
    HA_TOKEN=""
    interactive || fail "Check HA_URL and HA_TOKEN and run this again."
    if ! confirm "Try another token?" yes; then fail "Not connected. Run ./scripts/20-home-assistant.sh again later."; fi
  fi
done
unset HA_TOKEN
ok "Connected to Home Assistant $HA_VERSION ($HA_LOCATION) as $HA_USER"
info "$HA_ENTITIES entities; rooms: $(IFS=,; echo "${HA_AREAS[*]}" | sed 's/,/, /g')"
if [[ -n "$HA_ADMIN" ]]; then
  warn "This token belongs to an administrator. It works, but a separate user without admin rights is safer."
fi

# --- The kiosk's room ----------------------------------------------------------------------------
IDS=("${HA_AREA_IDS[@]}"); NAMES=("${HA_AREAS[@]}")
if (( ${#IDS[@]} == 0 )); then
  warn "Home Assistant has no areas (rooms) yet. Add them (Settings → Areas) and put devices in them: the kiosk is organised by room."
else
  CUR=$(in_container python -c 'import config; print(config.get()["home_area"])' 2>/dev/null | tr -d '\r' || true)
  OPTS=()
  for i in "${!IDS[@]}"; do [[ "${IDS[$i]}" == "$CUR" ]] && OPTS=("${IDS[$i]}|${NAMES[$i]}" "${OPTS[@]}") || OPTS+=("${IDS[$i]}|${NAMES[$i]}"); done
  # Without an answer: the current one, else a living room, else the first.
  if [[ -z "$CUR" ]]; then
    for i in "${!NAMES[@]}"; do [[ "${NAMES[$i],,}" == *living* || "${NAMES[$i],,}" == *lounge* ]] && { OPTS=("${IDS[$i]}|${NAMES[$i]}" "${OPTS[@]}"); break; }; done
  fi
  choose HOME_AREA "Which room does the kiosk hang in?" "${OPTS[@]}"
  [[ "$HOME_AREA" =~ ^[a-z0-9_]+$ ]] || fail "Not a room id: $HOME_AREA"
  in_container python -c "import config; config.update(home_area='$HOME_AREA')" >/dev/null
  ok "Kiosk room: $HOME_AREA (change it any time on the settings page)"
fi
