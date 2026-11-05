#!/bin/sh
# Registers ../fonts ("Kiosk Nunito") with fontconfig: the kiosk pages use it as a system font. As a web font,
# loaded again with every page, the Kindle's WebKit starts dropping letters after some hours.
# Undo: rm /var/local/font/conf.d/90-paperkiosk.conf (unregister.sh does it).
DIR=$(cd "$(dirname "$0")/.." && pwd)
CONF=/var/local/font/conf.d/90-paperkiosk.conf
if ! cmp -s "$DIR/fonts/90-paperkiosk.conf" "$CONF"; then
  cp "$DIR/fonts/90-paperkiosk.conf" "$CONF"
  echo "$(date +%T) font folder registered"
fi
fc-list | grep -q "Kiosk Nunito" || { fc-cache "$DIR/fonts"; echo "$(date +%T) font cache updated"; }
