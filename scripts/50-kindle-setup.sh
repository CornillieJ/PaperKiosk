#!/usr/bin/env bash
# Step 5: start the kiosk on the Kindle and check it works.
#   With SSH (step 4): does what "KUAL → PaperKiosk → Start kiosk" does, from here: registers the fullscreen app,
#   installs the font, keeps the screen on and opens the kiosk. Then a screenshot to data/kindle.png.
#   Without SSH: asks for that one tap, and waits until the Kindle shows up at the server (then you know it works,
#   and its IP is saved in .env).
# Unattended: KINDLE_IP (with SSH), WAIT_SECONDS (default 300).
source "$(dirname "$0")/lib.sh"

title "Start the kiosk on the Kindle" "the taps in KUAL, done for you when SSH works"
SCREEN=${SCREEN:-$(env_get SCREEN)}
if [[ -n "$SCREEN" && "$SCREEN" != kindle ]]; then ok "No Kindle (step 4: $SCREEN): nothing to do here."; exit 0; fi
compose ps --status running --services 2>/dev/null | grep -qx paperkiosk || fail "The server isn't running: ./scripts/30-start-server.sh"
WAIT=${WAIT_SECONDS:-300}
SINCE=$(date -u +%Y-%m-%dT%H:%M:%SZ)

wait_paired() {   # prints the IP of the first screen that pairs after SINCE (empty after WAIT seconds)
  local end=$((SECONDS + WAIT)) line
  while (( SECONDS < end )); do
    line=$(compose logs --no-log-prefix --since "$SINCE" paperkiosk 2>/dev/null | grep -E '^paired: [0-9a-fA-F.:]+ \(Kindle\)' | tail -1 || true)
    [[ -n "$line" ]] && { awk '{print $2}' <<<"$line"; return 0; }
    sleep 2
  done
}

screenshot() {
  kssh '/mnt/us/usbnet/bin/fbgrab /tmp/paperkiosk-shot.png >/dev/null 2>&1' 2>/dev/null &&
    kscp :/tmp/paperkiosk-shot.png "$DATA/kindle.png" 2>/dev/null && ok "Screenshot of the Kindle: data/kindle.png"
}

KINDLE_IP=${KINDLE_IP:-$(env_get KINDLE_IP)}
if [[ "$(env_get KINDLE_SSH)" == yes && -n "$KINDLE_IP" ]] && kindle_ssh_ok; then
  ok "Kindle reachable over SSH ($KINDLE_IP)"
  kssh 'test -f /mnt/us/extensions/paperkiosk/bin/start.sh' || fail "PaperKiosk isn't on the Kindle: run ./scripts/40-kindle-install.sh"
  spin "Starting the kiosk on the Kindle" kssh 'A=app://com.github.paperkiosk; lipc-set-prop com.lab126.appmgrd stop $A 2>/dev/null; sleep 2; cd /mnt/us/extensions/paperkiosk && sh bin/start.sh'
  IP=$(WAIT=60 wait_paired)
  [[ -n "$IP" ]] && ok "The Kindle opened the kiosk and paired" || warn "The Kindle didn't open the kiosk within a minute: check its Wi-Fi and data/kindle.png"
  sleep 8; screenshot || true
else
  explain <<EOF
**One tap on the Kindle** (the only one):

1. Open **KUAL** (it's a book in your library).
2. Tap **PaperKiosk**, then **Start kiosk (fullscreen, screen stays on)**.

The Kindle connects to the server; I'm watching for it (up to $((WAIT / 60)) minutes).
EOF
  IP=$(wait_paired)
  [[ -n "$IP" ]] || fail "No Kindle showed up. Is it on the same Wi-Fi? Does $(env_get PAPERKIOSK_URL)/health open in another browser? Then run this again."
  ok "The Kindle at $IP opened the kiosk and paired"
  env_set KINDLE_IP "$IP"; KINDLE_IP=$IP
  if [[ "$(env_get KINDLE_SSH)" == yes ]]; then
    for _ in $(seq 1 15); do kindle_ssh_ok && break; sleep 2; done
    if kindle_ssh_ok; then ok "SSH works: updates and screenshots run from here from now on"; screenshot || true
    else warn "SSH to the Kindle doesn't work (USBNetwork installed?). The kiosk runs anyway."; fi
  fi
fi
[[ -n "${IP:-}" ]] && env_set KINDLE_IP "$IP"

explain <<EOF
**Done!** The kiosk runs full screen and keeps the screen on.

- Settings (devices, names, pet, look): $(env_get PAPERKIOSK_URL)/config
- Give the Kindle a **fixed IP** in your router, and keep it on its charger.
- After the Kindle restarts: KUAL → PaperKiosk → Start kiosk (a restart clears it).
- Stop: KUAL → PaperKiosk → Stop kiosk. Remove: Uninstall kiosk app, then delete extensions/paperkiosk.
EOF
