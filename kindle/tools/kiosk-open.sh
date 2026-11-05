#!/usr/bin/env bash
# Show a kiosk page full screen on the Kindle (restarts the kiosk app), optionally screenshot it.
#   kiosk-open.sh /weather            -> open /weather, leave it there
#   kiosk-open.sh /weather out.png    -> open, wait, screenshot, then back to Home
# The app's start page is the iframe src in /mnt/us/extensions/paperkiosk/waf/index.html.
source "$(dirname "$0")/../../scripts/lib.sh"
P=${1:-/}; OUT=${2:-}; IDX=/mnt/us/extensions/paperkiosk/waf/index.html
[[ "$P" =~ ^/[A-Za-z0-9_./-]*$ ]] || fail "A path like /rooms or /room/kitchen"
LINK=$(kiosk_link); BASE=${LINK%%/?key=*}; KEY=${LINK##*key=}
setsrc() { kssh "sed -i 's#src=\"[^\"]*\"#src=\"$BASE$1?key=$KEY\"#' $IDX"; }
restart() { kssh 'A=app://com.github.paperkiosk; lipc-set-prop com.lab126.appmgrd stop $A; sleep 2; lipc-set-prop com.lab126.appmgrd start $A'; }
setsrc "$P"; restart
if [[ -n "$OUT" ]]; then
  sleep 10; "$(dirname "$0")/shot.sh" "$OUT"
  setsrc /; restart
fi
