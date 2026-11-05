#!/usr/bin/env bash
# Screenshot the Kindle's screen to a PNG here.  usage: kindle/tools/shot.sh [out.png]   (needs SSH, see install)
source "$(dirname "$0")/../../scripts/lib.sh"
pick_kindle   # more than one Kindle: asks which (KINDLE=<name> to choose ahead)
OUT=${1:-$DATA/kindle.png}   # (KINDLE=<name> or KINDLE_IP=<ip> in front: that Kindle)
kssh '/mnt/us/usbnet/bin/fbgrab /tmp/paperkiosk-shot.png >/dev/null 2>&1' || fail "SSH to the Kindle failed (KUAL → PaperKiosk → Enable SSH)"
kscp :/tmp/paperkiosk-shot.png "$OUT" && echo "$OUT"
