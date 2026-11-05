#!/usr/bin/env bash
# Step 5: start the kiosk on the Kindle and check it works.
#   With SSH (step 4): does what "KUAL → PaperKiosk → Start kiosk" does, from here: registers the fullscreen app,
#   installs the font, keeps the screen on and opens the kiosk. Then a screenshot to data/kindle.png.
#   Without SSH: asks for that one tap, and waits until the Kindle shows up at the server (then you know it works,
#   and its IP is saved in .env).
# Unattended: KINDLE_IP (with SSH), WAIT_SECONDS (default 300).
source "$(dirname "$0")/lib.sh"

title "Start the kiosk" "the KUAL taps, done for you when SSH works"
[[ "${ADDING:-0}" == 1 ]] || SCREEN=${SCREEN:-$(env_get SCREEN)}
if [[ -n "$SCREEN" && "$SCREEN" != kindle ]]; then ok "Not a KUAL device (step 4: $SCREEN): nothing to do here."; exit 0; fi
compose ps --status running --services 2>/dev/null | grep -qx paperkiosk || fail "The server isn't running: ./scripts/30-start-server.sh"
WAIT=${WAIT_SECONDS:-300}
SINCE=$(date -u +%Y-%m-%dT%H:%M:%SZ)


screenshot() {
  kssh '/mnt/us/usbnet/bin/fbgrab /tmp/paperkiosk-shot.png >/dev/null 2>&1' 2>/dev/null &&
    kscp :/tmp/paperkiosk-shot.png "$DATA/kindle.png" 2>/dev/null && ok "Screenshot of the screen: data/kindle.png"
}

if [[ "${ADDING:-0}" != 1 && -n "$(kindles_list)" ]]; then
  pick_kindle   # a saved Kindle (asks when there are more; KINDLE=<name> picks one); sets KINDLE_SSH too
  [[ "$KINDLE_IP" != "$(env_get KINDLE_IP)" ]] && ADDING=1   # not the first Kindle: .env stays as it is
fi
if [[ "${KINDLE_SSH:-}" == yes && -n "${KINDLE_IP:-}" ]] && kindle_ssh_ok; then
  ok "Device reachable over SSH ($KINDLE_IP)"
  kssh 'test -f /mnt/us/extensions/paperkiosk/bin/start.sh' || fail "PaperKiosk isn't on the device: run ./scripts/40-kindle-install.sh"
  spin "Starting the kiosk" kssh 'A=app://com.github.paperkiosk; lipc-set-prop com.lab126.appmgrd stop $A 2>/dev/null; sleep 2; cd /mnt/us/extensions/paperkiosk && sh bin/start.sh'
  IP=$(wait_paired "$SINCE" 60)
  [[ -n "$IP" ]] && ok "The device opened the kiosk and paired" || warn "The device didn't open the kiosk within a minute: check its Wi-Fi and data/kindle.png"
  sleep 8; screenshot || true
else
  explain <<EOF
**One tap on the device** (the only one): in **KUAL**, open **PaperKiosk** and tap
**Start kiosk (fullscreen, screen stays on)**.

The device connects to the server; I'm watching for it (up to $((WAIT / 60)) minutes).
EOF
  IP=$(wait_paired "$SINCE" "$WAIT")
  [[ -n "$IP" ]] || fail "Nothing showed up. Is it on the same Wi-Fi? Does $(env_get PAPERKIOSK_URL)/health open in another browser? Then run this again."
  if hidden_ip "$IP"; then   # Docker Desktop: the server doesn't see the device's own address
    ok "The device opened the kiosk and paired"
    IP=""
    if [[ "${KINDLE_SSH:-}" == yes ]]; then
      info "Docker Desktop doesn't show the server where screens connect from, so SSH needs the address by hand."
      ask IP "The device's IP address (in your router, or its Wi-Fi settings)" "" --required
    fi
  else
    ok "The device at $IP opened the kiosk and paired"
  fi
  if [[ -n "$IP" ]]; then save_env KINDLE_IP "$IP"; KINDLE_IP=$IP; export KINDLE_IP; fi
  if [[ "${KINDLE_SSH:-}" == yes ]]; then
    for _ in $(seq 1 15); do kindle_ssh_ok && break; sleep 2; done
    if kindle_ssh_ok; then ok "SSH works: updates and screenshots run from here from now on"; screenshot || true
    else warn "SSH to the device doesn't work (USBNetwork installed?). The kiosk runs anyway."; fi
  fi
fi
[[ -n "${IP:-}" ]] && ! { hidden_ip "$IP" && [[ "$IP" != "${KINDLE_IP:-}" ]]; } && save_env KINDLE_IP "$IP"
[[ "${ADDING:-0}" == 1 || -n "$(env_get KINDLE_NAME)" ]] || env_set KINDLE_NAME "KUAL device"

explain <<EOF
**Done!** The kiosk runs full screen and keeps the screen on.

- Settings (devices, names, pet, look): $(env_get PAPERKIOSK_URL)/config
- Give the device a **fixed IP** in your router, and keep it on its charger.
- After the device restarts: KUAL → PaperKiosk → Start kiosk (a restart clears it).
- Stop: KUAL → PaperKiosk → Stop kiosk. Remove: Uninstall kiosk app, then delete extensions/paperkiosk.
EOF
