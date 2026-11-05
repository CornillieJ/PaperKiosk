#!/bin/sh
# Removes the PaperKiosk app from the app registry and its font folder from fontconfig (the KUAL menu keeps working; Start re-registers).
A=com.github.paperkiosk
sqlite3 /var/local/appreg.db "delete from handlerIds where handlerId='$A'; delete from properties where handlerId='$A';"
rm -f /var/local/font/conf.d/90-paperkiosk.conf   # the "Kiosk Nunito" font folder (fonts.sh)
