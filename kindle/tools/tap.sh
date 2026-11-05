#!/usr/bin/env bash
# Simulate a finger tap on the Kindle at screen pixel X Y (PW3: 0..1071 x 0..1447).  usage: tap.sh 980 1400
# Uses evemu-event from USBNetwork on /dev/input/event1 (the touchscreen on a PW3; check others with evtest).
source "$(dirname "$0")/../../scripts/lib.sh"
X=${1:?x}; Y=${2:?y}; DEV=${TOUCH_DEV:-/dev/input/event1}
[[ "$X$Y" =~ ^[0-9]+$ ]] || fail "X and Y are numbers"
kssh "E=/mnt/us/usbnet/bin/evemu-event; D=$DEV
\$E \$D --type EV_ABS --code ABS_MT_SLOT --value 0
\$E \$D --type EV_ABS --code ABS_MT_TRACKING_ID --value 4242
\$E \$D --type EV_ABS --code ABS_MT_POSITION_X --value $X
\$E \$D --type EV_ABS --code ABS_MT_POSITION_Y --value $Y
\$E \$D --type EV_KEY --code BTN_TOUCH --value 1
\$E \$D --type EV_KEY --code BTN_TOOL_FINGER --value 1
\$E \$D --type EV_SYN --code SYN_REPORT --value 0 --sync
usleep 80000
\$E \$D --type EV_ABS --code ABS_MT_TRACKING_ID --value -1
\$E \$D --type EV_KEY --code BTN_TOUCH --value 0
\$E \$D --type EV_KEY --code BTN_TOOL_FINGER --value 0
\$E \$D --type EV_SYN --code SYN_REPORT --value 0 --sync"
