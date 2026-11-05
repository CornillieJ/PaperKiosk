#!/usr/bin/env bash
# Step 4: put PaperKiosk on the screen.
#   A device with KUAL: copies the KUAL extension (kindle/extension -> /mnt/us/extensions/paperkiosk) with your kiosk
#           link, over USB or over Wi-Fi (SSH), and optionally lets this server in over SSH (for step 5, updates and
#           screenshots). Anything else (a browser, another e-paper dashboard): shows the link; nothing to install.
# Getting KUAL onto a device is not part of PaperKiosk.
# Unattended: SCREEN=kindle|other|skip, KINDLE_METHOD=usb|ssh|folder, KINDLE_MOUNT=/media/you/Kindle,
#             KINDLE_IP=192.168.1.50, KINDLE_SSH=yes|no
# ADDING=1 (scripts/add-screen.sh): another screen; .env (the main Kindle's SCREEN/KINDLE_IP/KINDLE_SSH) stays as it is.
source "$(dirname "$0")/lib.sh"

title "Install on the screen" "the KUAL extension, or just the link for anything else"
secret_has kiosk_key || fail "Run ./scripts/10-configure.sh first."
[[ -n "$(env_get PAPERKIOSK_URL)" ]] || fail "No PAPERKIOSK_URL in .env: run ./scripts/10-configure.sh first."

choose SCREEN "Which screen?" \
  "kindle|A device that runs KUAL (installs the PaperKiosk extension)" \
  "other|Something else: a browser or another e-paper dashboard (just the link)" \
  "skip|Skip this step"
save_env SCREEN "$SCREEN"
case $SCREEN in
  skip) ok "Skipped."; exit 0 ;;
  other)
    explain <<EOF
Nothing to install on this screen: it only needs this link.

\`$(kiosk_link)\`

- **A browser** (tablet, phone, e-reader browser): open it once, then add it to the home screen or set it as
  the start page. The browser remembers it; after that $(env_get PAPERKIOSK_URL) works too.
- **An e-paper dashboard or screenshot service** that loads a URL by itself: give it the link as it is. It
  works on every request, also on devices that keep no cookies.

Pages are made for e-ink: about 600 × 750 CSS pixels (they scale to the screen), black and white.
The KUAL steps are skipped for this screen.
EOF
    exit 0 ;;
esac

explain <<'EOF'
This step installs a **KUAL extension**, so it assumes the device already runs KUAL and has an
**extensions** folder. Getting KUAL onto a device is not part of PaperKiosk and not covered here.

Optional: the **USBNetwork** extension (an SSH server). With it, this server can start the kiosk for you,
update it later and take screenshots, over Wi-Fi.
EOF

choose KINDLE_METHOD "How can I reach the device?" \
  "usb|Plugged into this server with a USB cable (first install)" \
  "ssh|Over Wi-Fi (SSH already works, e.g. an update)" \
  "folder|Neither: make a folder I copy over myself"

# --- SSH for the server? ----------------------------------------------------------------------------
KINDLE_SSH=${KINDLE_SSH:-}
if [[ -z "$KINDLE_SSH" ]]; then
  if [[ "$KINDLE_METHOD" == ssh ]]; then KINDLE_SSH=yes
  else
    explain <<'EOF'
**Let this server log in to the device over Wi-Fi?** Then the next step starts the kiosk by itself, and later
updates and screenshots work without touching the device. It uses USBNetwork's SSH server with a key that only
this server has (in `ssh/`), on Wi-Fi only. Note: USBNetwork's SSH also accepts the device's root password,
so only do this on a home network you trust.
EOF
    if confirm "Set up SSH for this server (needs USBNetwork)?" yes; then KINDLE_SSH=yes; else KINDLE_SSH=no; fi
  fi
fi
save_env KINDLE_SSH "$KINDLE_SSH"
if [[ "$KINDLE_SSH" == yes && ! -f "$KINDLE_KEY" ]]; then
  command -v ssh-keygen >/dev/null || fail "ssh-keygen is missing (install openssh-client), or answer no to SSH."
  mkdir -p "$SSHDIR" && chmod 700 "$SSHDIR"
  ssh-keygen -q -t ed25519 -N "" -C "paperkiosk-server" -f "$KINDLE_KEY"
  ok "New SSH key for the device: ssh/kindle_ed25519"
fi

# --- Stage the extension ----------------------------------------------------------------------------
STAGE=$(mktemp -d); trap 'rm -rf "$STAGE"' EXIT
EXT=$STAGE/paperkiosk
cp -r "$ROOT/kindle/extension" "$EXT"
LINK=$(kiosk_link)
ESC=$(printf '%s' "$LINK" | sed -e 's/[\\&#]/\\&/g')
sed -i.bak "s#__KIOSK_URL__#$ESC#" "$EXT/waf/index.html" && rm -f "$EXT/waf/index.html.bak"
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
      if [[ -n "$dev" ]] && confirm "The device ($dev) isn't mounted. Mount it?" yes; then
        MNT=$(udisksctl mount -b "$dev" 2>/dev/null | sed -n 's/.* at \(.*\)\.\{0,1\}$/\1/p' | sed 's/\.$//')
      fi
    fi
    if [[ -z "$MNT" ]] && is_wsl; then   # Windows: the drive has a letter; WSL shows it as /mnt/<letter>
      for m in /mnt/[d-z]; do [[ -d "$m/documents" && -d "$m/extensions" ]] && { MNT=$m; break; }; done
      if [[ -z "$MNT" ]] && interactive; then
        explain <<'EOF'
**On Windows:** open File Explorer and look up the device's **drive letter** (like `E:`). WSL only sees drives
that were there when it started, so the installer mounts it for you (it asks for your Linux password).
EOF
        LETTER=""; ask LETTER "Drive letter of the device" "" --required
        LETTER=$(tr -cd 'A-Za-z' <<<"$LETTER" | head -c1 | tr 'A-Z' 'a-z')
        [[ -n "$LETTER" ]] || fail "That's not a drive letter."
        if [[ ! -d "/mnt/$LETTER/documents" ]]; then
          sudo mkdir -p "/mnt/$LETTER" && sudo mount -t drvfs "${LETTER^^}:" "/mnt/$LETTER" -o metadata ||
            fail "Could not mount ${LETTER^^}: (sudo mount -t drvfs ${LETTER^^}: /mnt/$LETTER)"
        fi
        MNT=/mnt/$LETTER
      fi
    fi
    [[ -n "$MNT" ]] && ok "Device found at $MNT"
    ask MNT "Where is the device's drive mounted?" "${MNT:-}" --required
    [[ -d "$MNT/documents" ]] || fail "$MNT doesn't look like the device's drive (no documents folder)."
    [[ -d "$MNT/extensions" ]] || fail "No extensions folder on $MNT: this device doesn't have KUAL set up."
    rm -rf "$MNT/extensions/paperkiosk"
    cp -r "$EXT" "$MNT/extensions/"
    [[ "$KINDLE_SSH" == yes ]] && (cd "$MNT" && sh -c "$USBNET_FIX" | sed 's/^/  /')
    sync
    ok "Copied to $MNT/extensions/paperkiosk"
    if command -v udisksctl >/dev/null && dev=$(findmnt -no SOURCE "$MNT" 2>/dev/null) && [[ -n "$dev" ]] &&
       confirm "Eject the device now?" yes; then
      udisksctl unmount -b "$dev" >/dev/null && udisksctl power-off -b "$dev" >/dev/null 2>&1 || true
      ok "Ejected: you can unplug it."
    elif is_wsl; then
      info "Eject the device in Windows before unplugging it (the USB icon in the taskbar, or right-click the drive in File Explorer)."
    else
      info "Eject the device safely before unplugging it."
    fi
    ;;
  ssh)
    if [[ "${ADDING:-0}" != 1 && -n "$(kindles_list)" ]]; then
      pick_kindle   # a saved Kindle (asks when there are more; KINDLE=<name> picks one)
      [[ "$KINDLE_IP" != "$(env_get KINDLE_IP)" ]] && ADDING=1   # not the first Kindle: .env stays as it is
    fi
    ask KINDLE_IP "The device's IP address" "${KINDLE_IP:-}" --required
    export KINDLE_IP
    save_env KINDLE_IP "$KINDLE_IP"
    if ! kindle_ssh_ok; then
      explain <<'EOF'
This server's key isn't on the device yet. Log in once with its root password (or your own key);
the installer then adds its key. Root password unknown? Use the USB method instead.
EOF
      interactive || fail "Can't log in to root@$KINDLE_IP. Use KINDLE_METHOD=usb."
      ssh -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$SSHDIR/kindle_known_hosts" "root@$KINDLE_IP" \
        'mkdir -p /mnt/us/usbnet/etc && cat >> /mnt/us/usbnet/etc/authorized_keys' < "$KINDLE_KEY.pub" ||
        fail "Could not log in to root@$KINDLE_IP"
      kindle_ssh_ok || fail "The key was added but logging in with it fails. Restart SSH on the device (KUAL → USBNetwork) and try again."
    fi
    kssh 'mkdir -p /mnt/us/extensions/paperkiosk' && kscp -r "$EXT"/. :/mnt/us/extensions/paperkiosk/
    kssh "cd /mnt/us && $USBNET_FIX" | sed 's/^/  /'
    ok "Copied to the device over Wi-Fi"
    ;;
  folder)
    OUT=$DATA/kindle-extension
    rm -rf "$OUT"; mkdir -p "$OUT"; cp -r "$EXT" "$OUT/"
    explain <<EOF
Ready in \`$OUT/paperkiosk\`. Copy that **paperkiosk** folder into the **extensions** folder of KUAL on the
device (over USB, it shows up as a drive), then eject it.
EOF
    if is_wsl && command -v wslpath >/dev/null; then info "In Windows File Explorer: $(wslpath -w "$OUT/paperkiosk")"; fi
    ;;
esac
explain <<'EOF'
Next: **./scripts/50-kindle-setup.sh** starts the kiosk (by itself over Wi-Fi, or with one tap in KUAL).
EOF
