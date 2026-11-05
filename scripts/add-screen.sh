#!/usr/bin/env bash
# Add another screen to a PaperKiosk that is already set up: a second Kindle, an old tablet, a phone, ...
#   1. a name for it, and what it is
#   2. Kindle: the app goes on it (USB, Wi-Fi or a folder) and the kiosk starts (same as steps 4 and 5);
#      other screens: the kiosk link (and a QR code with qrencode) to open once
#   3. waits until it pairs, so its IP is known
#   4. optionally its own settings (room, Home cards, pet, ...): listed under "Screens" on the settings page
# Your first Kindle's settings in .env (KINDLE_IP, ...) are not changed.
# Unattended: SCREEN_NAME, SCREEN=kindle|other, OWN_SETTINGS=yes|no, SCREEN_ROOM=<area id>, plus the step 4 variables.
source "$(dirname "$0")/lib.sh"

title "Add a screen" "another KUAL device, a tablet, an e-paper dashboard, ..."
secret_has kiosk_key && secret_has admin_password || fail "PaperKiosk isn't set up yet: run ./install.sh first."
compose ps --status running --services 2>/dev/null | grep -qx paperkiosk || fail "The server isn't running: ./scripts/30-start-server.sh"

ask SCREEN_NAME "A name for the new screen" "" --required
SCREEN_NAME=$(tr -d '\t\r\n' <<<"$SCREEN_NAME" | cut -c1-30)
choose SCREEN "What is it?" \
  "kindle|A device that runs KUAL (installs the PaperKiosk extension)" \
  "other|Something else: a browser or another e-paper dashboard (just the link)"

SINCE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
IP=""
if [[ "$SCREEN" == kindle ]]; then
  export ADDING=1 ADD_STATE; ADD_STATE=$(mktemp); trap 'rm -f "$ADD_STATE"' EXIT
  SCREEN=kindle "$ROOT/scripts/40-kindle-install.sh" || exit 1
  # shellcheck disable=SC1090
  source "$ADD_STATE"   # KINDLE_SSH, KINDLE_IP chosen in step 4
  export KINDLE_SSH KINDLE_IP
  SCREEN=kindle "$ROOT/scripts/50-kindle-setup.sh" || exit 1
  # shellcheck disable=SC1090
  source "$ADD_STATE"
  IP=${KINDLE_IP:-}
  if [[ -n "$IP" ]]; then
    if [[ -z "$(env_get KINDLE_IP)" ]]; then   # the first Kindle: it goes in .env
      env_set KINDLE_IP "$IP"; env_set KINDLE_NAME "$SCREEN_NAME"; env_set KINDLE_SSH "${KINDLE_SSH:-no}"
    else
      kindle_add "$SCREEN_NAME" "$IP" "${KINDLE_SSH:-no}"
    fi
    ok "Saved: kindle/tools and updates now offer $SCREEN_NAME too"
  fi
else
  explain <<'EOF'
Open this link **once** on the new screen (type it, or scan the QR code), then add it to the home screen or
set it as the browser's start page. The screen stays paired after that.
EOF
  show_link
  if confirm "Wait here until the screen has opened it (so it can get its own settings)?" yes; then
    info "Waiting for the screen to open the link..."
    IP=$(wait_paired "$SINCE" "${WAIT_SECONDS:-300}" any)
    if [[ -n "$IP" ]]; then ok "Paired: the screen at $IP"; else warn "Nothing opened the link within $(( ${WAIT_SECONDS:-300} / 60 )) minutes."; fi
  fi
fi

# --- Its own settings --------------------------------------------------------------------------------
if [[ -n "$IP" ]] && hidden_ip "$IP"; then
  info "Docker Desktop (Windows, macOS) doesn't show the server where screens connect from, so screens can't get"
  info "settings of their own here: every screen uses the main settings."
  exit 0
fi
if [[ -z "$IP" ]]; then
  info "It uses the main settings. Own settings later: settings page → Screens → Add a screen (with its IP)."
  exit 0
fi
explain <<EOF
**$SCREEN_NAME** shows the main settings now (same room, Home cards and pet as your other screen).
It can have its own instead: another room on Home, other cards, another pet, other tabs, ... It is recognised by
its IP address ($IP), so give it a **fixed IP** in your router.
EOF
OWN_SETTINGS=${OWN_SETTINGS:-}
if [[ -z "$OWN_SETTINGS" ]]; then confirm "Give $SCREEN_NAME its own settings?" yes && OWN_SETTINGS=yes || OWN_SETTINGS=no; fi
[[ "$OWN_SETTINGS" == yes ]] || { ok "Done: $SCREEN_NAME uses the main settings."; exit 0; }

if [[ -z "${SCREEN_ROOM:-}" ]]; then
  out=$(in_container python screens.py areas 2>/dev/null | tr -d '\r' | grep -E '^PK_AREA(S|_IDS)=') || true
  eval "$out"   # quoted by screens.py (shlex.quote)
  opts=("|The same room as the main screen")
  for i in "${!PK_AREA_IDS[@]}"; do opts+=("${PK_AREA_IDS[$i]}|${PK_AREAS[$i]}"); done
  (( ${#opts[@]} > 1 )) && choose SCREEN_ROOM "Which room is $SCREEN_NAME in?" "${opts[@]}"
fi
[[ -z "${SCREEN_ROOM:-}" || "$SCREEN_ROOM" =~ ^[a-z0-9_]+$ ]] || fail "Not a room id: $SCREEN_ROOM"
ID=$(in_container python screens.py add "$SCREEN_NAME" "$IP" ${SCREEN_ROOM:+"$SCREEN_ROOM"} | tr -d '\r' | tail -1) ||
  fail "Could not save the screen."
ok "$SCREEN_NAME has its own settings (it shows them within a few seconds)"
explain <<EOF
Change them on the settings page: **$(env_get PAPERKIOSK_URL)/config?kiosk=$ID**
(or pick **$SCREEN_NAME** at the top of the settings page). Settings marked *this screen* are its own.
EOF
