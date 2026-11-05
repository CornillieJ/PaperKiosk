#!/usr/bin/env bash
# Step 1: the server's settings (.env) and its keys (./secrets):
#   - port, address screens use, time zone, file owner
#   - kiosk_key: the key a screen needs once to pair (made here, kept on later runs; --new-key makes a new one,
#     which un-pairs every screen)
#   - admin_password: the password for the settings page (/config), stored as a PBKDF2 hash
# Unattended: PAPERKIOSK_PORT, PAPERKIOSK_URL, TZ, ADMIN_PASSWORD (see lib.sh).
source "$(dirname "$0")/lib.sh"
NEW_KEY=0; NEW_PASSWORD=0
for a in "$@"; do case $a in --new-key) NEW_KEY=1 ;; --new-password) NEW_PASSWORD=1 ;; esac; done

title "Configure PaperKiosk" "port, address, time zone, keys and the settings password"
env_init; ensure_dirs

# Port and address
PORT_DEF=$(env_get PAPERKIOSK_PORT); PORT_DEF=${PORT_DEF:-8100}
ask PAPERKIOSK_PORT "Port for PaperKiosk on this server" "$PORT_DEF"
[[ "$PAPERKIOSK_PORT" =~ ^[0-9]+$ && $PAPERKIOSK_PORT -ge 1 && $PAPERKIOSK_PORT -le 65535 ]] || fail "Not a port: $PAPERKIOSK_PORT"
if ! docker ps --format '{{.Names}}' | grep -qx paperkiosk; then
  if (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | awk '{print $4}' | grep -qE "[:.]$PAPERKIOSK_PORT\$"; then
    warn "Something already listens on port $PAPERKIOSK_PORT; pick another one if the server doesn't start."
  fi
fi
env_set PAPERKIOSK_PORT "$PAPERKIOSK_PORT"

IP=$(lan_ip || true)
URL_DEF=$(env_get PAPERKIOSK_URL)
[[ -z "$URL_DEF" || "$URL_DEF" == *":$PORT_DEF" && "$PORT_DEF" != "$PAPERKIOSK_PORT" ]] && URL_DEF="http://${IP:-<this-server-ip>}:$PAPERKIOSK_PORT"
explain <<EOF
Screens reach PaperKiosk over your home network. This is the address they use: this server's **LAN IP** and the
port. Give this server a fixed IP in your router (a "DHCP reservation"), or screens lose it one day.
EOF
ask PAPERKIOSK_URL "Address for screens" "$URL_DEF" --required
PAPERKIOSK_URL=${PAPERKIOSK_URL%/}
[[ "$PAPERKIOSK_URL" =~ ^https?://[^/?#\"\'\<\>\ ]+$ ]] || fail "Use a plain address like http://192.168.1.10:$PAPERKIOSK_PORT"
env_set PAPERKIOSK_URL "$PAPERKIOSK_URL"
env_set PAPERKIOSK_BIND "$(env_get PAPERKIOSK_BIND | grep . || echo 0.0.0.0)"

# Time zone
TZ_DEF=$(env_get TZ)
if [[ -z "$TZ_DEF" ]]; then   # this machine's own time zone
  TZ_DEF=$(timedatectl show -p Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null ||
           readlink /etc/localtime 2>/dev/null | sed 's#.*/zoneinfo/##' || true)
fi
TZ_ANSWER=${TZ_ANSWER:-}
ask TZ_ANSWER "Time zone (for the clock and the downtime hours)" "${TZ_DEF:-UTC}"
[[ "$TZ_ANSWER" =~ ^[A-Za-z0-9_+/-]{1,60}$ ]] || fail "Not a time zone name: $TZ_ANSWER"
env_set TZ "$TZ_ANSWER"

env_set PUID "$(id -u)"; env_set PGID "$(id -g)"

# Kiosk key
if [[ "$NEW_KEY" == 1 ]] || ! secret_has kiosk_key; then
  if secret_has kiosk_key; then warn "A new key un-pairs every screen: run the Kindle step again afterwards."; fi
  head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' | secret_set kiosk_key
  ok "New kiosk key in secrets/kiosk_key"
else
  ok "Kiosk key: kept (secrets/kiosk_key; ./scripts/10-configure.sh --new-key makes a new one)"
fi

# Settings password
hash_pw() {   # password on stdin -> PBKDF2 hash, with Python here or in a throw-away container
  if command -v python3 >/dev/null 2>&1; then python3 "$ROOT/server/app/auth.py" hash
  else docker run --rm -i -v "$ROOT/server/app/auth.py:/auth.py:ro" python:3.12-alpine python /auth.py hash; fi
}
if [[ "$NEW_PASSWORD" == 1 ]] || ! secret_has admin_password; then
  explain <<'EOF'
The **settings page** (`/config`) is where you pick devices, names and the look. It needs a password: anyone
on your network could otherwise change your kiosk. At least 8 characters.
EOF
  FROM_ENV=${ADMIN_PASSWORD:+1}
  while :; do
    ADMIN_PASSWORD=${ADMIN_PASSWORD:-}
    ask ADMIN_PASSWORD "Password for the settings page" "" --password --required
    if [[ ${#ADMIN_PASSWORD} -lt 8 ]]; then warn "At least 8 characters, please."; ADMIN_PASSWORD="" FROM_ENV=""; continue; fi
    if interactive && [[ -z "$FROM_ENV" ]]; then   # typed by hand: once more to catch typos
      AGAIN=""; ask AGAIN "Same password again" "" --password --required
      [[ "$AGAIN" == "$ADMIN_PASSWORD" ]] || { warn "They don't match, once more."; ADMIN_PASSWORD=""; continue; }
    fi
    break
  done
  printf '%s\n' "$ADMIN_PASSWORD" | hash_pw | secret_set admin_password
  unset ADMIN_PASSWORD AGAIN
  ok "Settings password saved (as a hash) in secrets/admin_password"
else
  ok "Settings password: kept (./scripts/10-configure.sh --new-password to change it)"
fi
ok "Saved in .env"
