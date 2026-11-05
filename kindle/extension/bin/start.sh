#!/bin/sh
# Keep the screen on and open the kiosk as its own mesquite app (../waf), which has no browser bar.
# The app is registered in the app registry once (see register.sh), the font installed (fonts.sh); SSH for the
# server is started too, and the nightly restart (nightly.sh).
LOG=/mnt/us/paperkiosk.log
DIR=$(dirname "$0")

echo "== start $(date)" > "$LOG"
"$DIR/ssh.sh"
"$DIR/register.sh" >> "$LOG" 2>&1
"$DIR/fonts.sh" >> "$LOG" 2>&1
setsid sh "$DIR/nightly.sh" > /dev/null 2>&1 < /dev/null &   # restarts the app at 04:00 (replaces an older loop)
lipc-set-prop com.lab126.powerd preventScreenSaver 1
lipc-set-prop com.lab126.cmd wirelessEnable 1
lipc-set-prop com.lab126.appmgrd start app://com.github.paperkiosk
