#!/bin/sh
# Screenshots of kiosk pages at the Kindle's size (597x750 CSS px, as in the kiosk app), headless Chrome.
# Usage: tests/shots.sh OUTDIR [BASE_URL] [path ...]   (default base http://localhost:8101, the demo server;
# KEY=<kiosk key> for another server, default "demo")
mkdir -p "${1:?outdir}"; out=$(realpath "$1"); shift
base=${1:-http://localhost:8101}; [ $# -gt 0 ] && shift
[ $# -gt 0 ] || set -- / /rooms /room/living_room /lights /lights/week /weather /info /settings \
  /device/light.sidebar_leds /device/climate.living_room_ac /device/media_player.tv
for p in "$@"; do
  name=$(echo "$p" | sed 's#^/##; s#[/?=&]#_#g'); [ -n "$name" ] || name=home
  docker run --rm --network host -v "$out":/out zenika/alpine-chrome --no-sandbox --hide-scrollbars \
    --force-device-scale-factor=1.796 --window-size=597,750 --virtual-time-budget=3000 \
    --screenshot=/out/"$name".png "$base$p$(case $p in *\?*) echo "&" ;; *) echo "?" ;; esac)key=${KEY:-demo}" >/dev/null 2>&1
  echo "$out/$name.png"
done
