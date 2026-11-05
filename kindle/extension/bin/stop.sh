#!/bin/sh
# Back to normal: close the kiosk app and let the Kindle sleep again.
rm -f /var/run/paperkiosk.run   # ends nightly.sh
lipc-set-prop com.lab126.appmgrd stop app://com.github.paperkiosk 2>/dev/null
lipc-set-prop com.lab126.powerd preventScreenSaver 0
