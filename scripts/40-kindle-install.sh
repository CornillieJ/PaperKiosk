#!/usr/bin/env bash
# Step 4: put the PaperKiosk app on the screen.
#   Kindle: copies the KUAL extension (kindle/extension -> /mnt/us/extensions/paperkiosk) with your kiosk link,
#           over USB or over Wi-Fi (SSH), and optionally lets this server in over SSH (for step 5, updates and
#           screenshots). Other screens: shows the link to open in their browser.
# Unattended: SCREEN=kindle|other|skip, KINDLE_METHOD=usb|ssh|folder, KINDLE_MOUNT=/media/you/Kindle,
#             KINDLE_IP=192.168.1.50, KINDLE_SSH=yes|no
source "$(dirname "$0")/lib.sh"

title "Install on the screen" "the Kindle app (a KUAL extension), or a link for any other screen"
secret_has kiosk_key || fail "Run ./scripts/10-configure.sh first."
[[ -n "$(env_get PAPERKIOSK_URL)" ]] || fail "No PAPERKIOSK_URL in .env: run ./scripts/10-configure.sh first."

choose SCREEN "Which screen?" \
  "kindle|A jailbroken Kindle (with KUAL)" \
  "other|Another screen with a browser (tablet, Kobo, old phone, ...)" \
  "skip|Skip this step"
env_set SCREEN "$SCREEN"
case $SCREEN in
  skip) ok "Skipped."; exit 0 ;;
  other)
    explain <<EOF
Open this link once in the screen's browser, then add it to the home screen / set it as the start page:

\`$(kiosk_link)\`

The screen remembers it (a cookie): after that the plain address $(env_get PAPERKIOSK_URL) works too.
The pages are made for e-ink: about 600 × 750 CSS pixels, black and white, few redraws.
EOF
    exit 0 ;;
esac

explain <<'EOF'
**What the Kindle needs first** (once, by hand; it can't be automated):

1. A **jailbreak** and **KUAL** (the Kindle launcher for extensions). Follow https://kindlemodding.org for your
   model and firmware. Tested on a Paperwhite 3 (7th gen) with firmware 5.14; other touch Kindles on 5.x should work.
2. Optional, but it makes everything automatic: **USBNetwork** (on kindlemodding.org too). With it, this server
   can start the kiosk for you, update it later and take screenshots, over Wi-Fi.
EOF

choose KINDLE_METHOD "How can I reach the Kindle?" \
  "usb|Plugged into this server with a USB cable (first install)" \
  "ssh|Over Wi-Fi (SSH already works, e.g. an update)" \
  "folder|Neither: make a folder I copy over myself"

# --- SSH for the server? ----------------------------------------------------------------------------
KINDLE_SSH=${KINDLE_SSH:-}
if [[ -z "$KINDLE_SSH" ]]; then
  if [[ "$KINDLE_METHOD" == ssh ]]; then KINDLE_SSH=yes
  else
    explain <<'EOF'
**Let this server log in to the Kindle over Wi-Fi?** Then the next step starts the kiosk by itself, and later
updates and screenshots work without touching the Kindle. It uses USBNetwork's SSH server with a key that only
this server has (in `secrets/`), on Wi-Fi only. Note: USBNetwork's SSH also accepts the Kindle's root password,
so only do this on a home network you trust.
EOF
    if confirm "Set up SSH for this server (needs USBNetwork)?" yes; then KINDLE_SSH=yes; else KINDLE_SSH=no; fi
  fi
fi
env_set KINDLE_SSH "$KINDLE_SSH"
if [[ "$KINDLE_SSH" == yes && ! -f "$KINDLE_KEY" ]]; then
  command -v ssh-keygen >/dev/null || fail "ssh-keygen is missing (install openssh-client), or answer no to SSH."
  ssh-keygen -q -t ed25519 -N "" -C "paperkiosk-server" -f "$KINDLE_KEY"
  ok "New SSH key for the Kindle: secrets/kindle_ed25519"
fi

# --- Stage the extension ----------------------------------------------------------------------------
STAGE=$(mktemp -d); trap 'rm -rf "$STAGE"' EXIT
EXT=$STAGE/paperkiosk
cp -r "$ROOT/kindle/extension" "$EXT"
LINK=$(kiosk_link)
sed -i.bak "s#__KIOSK_URL__#${LINK//#/\\#}#" "$EXT/waf/index.html" && rm -f "$EXT/waf/index.html.bak"
grep -q "__KIOSK_URL__" "$EXT/waf/index.html" && fail "Could not put the kiosk link in waf/index.html"
[[ "$KINDLE_SSH" == yes ]] && cp "$KINDLE_KEY.pub" "$EXT/authorized_keys"

# Dropbear + SSH over Wi-Fi only (USB drive mode keeps working); the old usbnet config is kept as .bak-paperkiosk.
USBNET_FIX='c=usbnet/etc/config; [ -f $c ] || { echo "USBNetwork is not installed: no SSH (the kiosk itself works)"; exit 0; }
[ -f $c.bak-paperkiosk ] || cp $c $c.bak-paperkiosk
sed -i -e "s/^USE_OPENSSH=.*/USE_OPENSSH=\"false\"/" -e "s/^USE_WIFI=.*/USE_WIFI=\"true\"/" -e "s/^USE_WIFI_SSHD_ONLY=.*/USE_WIFI_SSHD_ONLY=\"true\"/" $c
cp extensions/paperkiosk/authorized_keys usbnet/etc/authorized_keys 2>/dev/null
echo "USBNetwork: dropbear, SSH over Wi-Fi only"'

case $KINDLE_METHOD in
  usb)
    MNT=${KINDLE_MOUNT:-}
    if [[ -z "$MNT" ]]; then
      for m in /media/*/Kindle /run/media/*/Kindle /media/Kindle /mnt/Kindle /Volumes/Kindle; do [[ -d "$m/documents" ]] && { MNT=$m; break; }; done
    fi
    if [[ -z "$MNT" ]] && command -v udisksctl >/dev/null && interactive; then
      dev=$(lsblk -rpo NAME,LABEL 2>/dev/null | awk '$2=="Kindle"{print $1; exit}')
      if [[ -n "$dev" ]] && confirm "The Kindle ($dev) isn't mounted. Mount it?" yes; then
        MNT=$(udisksctl mount -b "$dev" 2>/dev/null | sed -n 's/.* at \(.*\)\.\{0,1\}$/\1/p' | sed 's/\.$//')
      fi
    fi
    [[ -n "$MNT" ]] && ok "Kindle found at $MNT"
    ask MNT "Where is the Kindle mounted?" "${MNT:-}" --required
    [[ -d "$MNT/documents" ]] || fail "$MNT doesn't look like a Kindle (no documents folder)."
    [[ -d "$MNT/extensions" ]] || fail "No extensions folder on the Kindle: install KUAL first (https://kindlemodding.org)."
    rm -rf "$MNT/extensions/paperkiosk"
    cp -r "$EXT" "$MNT/extensions/"
    [[ "$KINDLE_SSH" == yes ]] && (cd "$MNT" && sh -c "$USBNET_FIX" | sed 's/^/  /')
    sync
    ok "Copied to $MNT/extensions/paperkiosk"
    if command -v udisksctl >/dev/null && dev=$(findmnt -no SOURCE "$MNT" 2>/dev/null) && [[ -n "$dev" ]] &&
       confirm "Eject the Kindle now?" yes; then
      udisksctl unmount -b "$dev" >/dev/null && udisksctl power-off -b "$dev" >/dev/null 2>&1 || true
      ok "Ejected: you can unplug it."
    else
      info "Eject the Kindle safely before unplugging it."
    fi
    ;;
  ssh)
    KINDLE_IP=${KINDLE_IP:-$(env_get KINDLE_IP)}
    ask KINDLE_IP "The Kindle's IP address" "${KINDLE_IP:-}" --required
    env_set KINDLE_IP "$KINDLE_IP"
    if ! kindle_ssh_ok; then
      explain <<'EOF'
This server's key isn't on the Kindle yet. Log in once with the Kindle's root password (or your own key);
the installer then adds its key. Root password unknown? Use the USB method instead.
EOF
      interactive || fail "Can't log in to root@$KINDLE_IP. Use KINDLE_METHOD=usb."
      ssh -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$SECRETS/kindle_known_hosts" "root@$KINDLE_IP" \
        'mkdir -p /mnt/us/usbnet/etc && cat >> /mnt/us/usbnet/etc/authorized_keys' < "$KINDLE_KEY.pub" ||
        fail "Could not log in to root@$KINDLE_IP"
      kindle_ssh_ok || fail "The key was added but logging in with it fails. Restart SSH on the Kindle (KUAL → USBNetwork) and try again."
    fi
    kssh 'mkdir -p /mnt/us/extensions/paperkiosk' && kscp -r "$EXT"/. :/mnt/us/extensions/paperkiosk/
    kssh "cd /mnt/us && $USBNET_FIX" | sed 's/^/  /'
    ok "Copied to the Kindle over Wi-Fi"
    ;;
  folder)
    OUT=$DATA/kindle-extension
    rm -rf "$OUT"; mkdir -p "$OUT"; cp -r "$EXT" "$OUT/"
    explain <<EOF
Ready in \`$OUT/paperkiosk\`. Copy that **paperkiosk** folder into the **extensions** folder on the Kindle
(plug it in over USB; it shows up as a drive called Kindle), then eject it.
EOF
    ;;
esac
explain <<'EOF'
Next: **./scripts/50-kindle-setup.sh** starts the kiosk (by itself over Wi-Fi, or with one tap on the Kindle).
EOF
