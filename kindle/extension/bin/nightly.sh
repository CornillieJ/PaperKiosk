#!/bin/sh
# Restarts the kiosk app every night at 04:00 while the kiosk runs (start.sh starts this, stop.sh ends it):
# a fresh browser every day, nothing that builds up over days of reloading (the screen flashes once, at 4).
APP=app://com.github.paperkiosk
FLAG=/var/run/paperkiosk.run
echo $$ > "$FLAG"
while [ "$(cat "$FLAG" 2>/dev/null)" = "$$" ]; do
  sleep 50
  if [ "$(date +%H%M)" = "0400" ]; then
    echo "$(date +%T) nightly restart" >> /mnt/us/paperkiosk.log
    lipc-set-prop com.lab126.appmgrd stop $APP 2>/dev/null
    sleep 3
    lipc-set-prop com.lab126.appmgrd start $APP
    sleep 60
  fi
done
