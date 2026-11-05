#!/bin/sh
# Lets the PaperKiosk server (key in ../authorized_keys, only there when the installer set up SSH) in over SSH: installs the key for root and starts
# USBNetwork's sshd. usbnet is configured Wi-Fi-only (USE_WIFI_SSHD_ONLY), so USB drive mode keeps
# working; it also opens port 22 on wlan0. Uses dropbear (USE_OPENSSH=false in usbnet/etc/config):
# OpenSSH refuses the host keys on the FAT userstore (world-readable) and exits silently. Root's home is on tmpfs, hence redone on every start.
KEYS="$(dirname "$0")/../authorized_keys"
LOG=/mnt/us/paperkiosk.log
[ -s "$KEYS" ] || { echo "$(date +%T) ssh: not set up (no authorized_keys from the installer)" >> "$LOG"; exit 0; }
[ -x /mnt/us/usbnet/bin/usbnetwork ] || { echo "$(date +%T) ssh: USBNetwork is not installed" >> "$LOG"; exit 0; }
H=$(awk -F: '$1=="root"{print $6}' /etc/passwd)
for d in "${H:-/tmp/root}/.ssh" /tmp/root/.ssh; do
  mkdir -p "$d" && cp "$KEYS" "$d/authorized_keys" && chmod 700 "$d" && chmod 600 "$d/authorized_keys"
done
cp "$KEYS" /mnt/us/usbnet/etc/authorized_keys
# usbnetwork is a toggle: only call it when no sshd runs, or it would stop it.
if pgrep dropbear >/dev/null 2>&1 || pgrep -f usbnet/sbin/sshd >/dev/null 2>&1; then
  echo "$(date +%T) ssh: already running (home ${H})" >> "$LOG"
else
  /mnt/us/usbnet/bin/usbnetwork >> "$LOG" 2>&1
  echo "$(date +%T) ssh: started (home ${H}), ip $(ifconfig wlan0 | grep -o 'inet addr:[0-9.]*')" >> "$LOG"
fi
