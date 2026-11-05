#!/usr/bin/env bash
# Tap at X Y on the Kindle and print when the screen content (framebuffer row ROW, default: the tab bar)
# changed, in ms after the finger lifted. Paint time, not the e-ink waveform. Usage: taptime.sh X Y [ROW]
# (PW3 framebuffer: stride 1088 bytes, 8 bits per pixel; other models differ.)
source "$(dirname "$0")/../../scripts/lib.sh"
pick_kindle   # more than one Kindle: asks which (KINDLE=<name> to choose ahead)
X=${1:?x}; Y=${2:?y}; ROW=${3:-1385}
[[ "$X$Y$ROW" =~ ^[0-9]+$ ]] || fail "numbers only"
kssh "cat > /tmp/taptime.sh" <<'DEV'
X=$1; Y=$2; ROW=$3
E=/mnt/us/usbnet/bin/evemu-event; D=/dev/input/event1
sum() { dd if=/dev/fb0 bs=1088 skip=$ROW count=1 2>/dev/null | md5sum; }
up() { cut -d' ' -f1 /proc/uptime | tr -d .; }
prev=$(sum); t0=$(up)
$E $D --type EV_ABS --code ABS_MT_SLOT --value 0
$E $D --type EV_ABS --code ABS_MT_TRACKING_ID --value 4242
$E $D --type EV_ABS --code ABS_MT_POSITION_X --value $X
$E $D --type EV_ABS --code ABS_MT_POSITION_Y --value $Y
$E $D --type EV_KEY --code BTN_TOUCH --value 1
$E $D --type EV_KEY --code BTN_TOOL_FINGER --value 1
$E $D --type EV_SYN --code SYN_REPORT --value 0 --sync
usleep 80000
$E $D --type EV_ABS --code ABS_MT_TRACKING_ID --value -1
$E $D --type EV_KEY --code BTN_TOUCH --value 0
$E $D --type EV_KEY --code BTN_TOOL_FINGER --value 0
$E $D --type EV_SYN --code SYN_REPORT --value 0 --sync
t1=$(up)
while [ $(( $(up) - t0 )) -lt 400 ]; do
  s=$(sum); [ "$s" != "$prev" ] && { echo "screen changed $(( ($(up) - t1) * 10 )) ms after release"; prev=$s; }
done
DEV
kssh "sh /tmp/taptime.sh $X $Y $ROW; true"
