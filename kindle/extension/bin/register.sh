#!/bin/sh
# Registers ../waf as app com.github.paperkiosk in /var/local/appreg.db (persists across reboots).
# Undo: bin/unregister.sh. A backup of the registry from before the first install: /mnt/us/appreg.db.bak-paperkiosk
A=com.github.paperkiosk
R=/var/local/appreg.db
[ -f /mnt/us/appreg.db.bak-paperkiosk ] || cp "$R" /mnt/us/appreg.db.bak-paperkiosk
if [ -z "$(sqlite3 "$R" "select handlerId from handlerIds where handlerId='$A'")" ]; then
  sqlite3 "$R" "insert into handlerIds values ('$A');
    insert into properties (handlerId,name,value) values ('$A','command','/usr/bin/mesquite -l $A -c file:///mnt/us/extensions/paperkiosk/waf/');
    insert into properties (handlerId,name,value) values ('$A','unloadPolicy','unloadOnPause');"
  echo "$(date +%T) registered $A"
fi
