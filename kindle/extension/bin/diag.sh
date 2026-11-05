#!/bin/sh
# Read-only: collects what the fullscreen options depend on into /mnt/us/paperkiosk-diag.txt.
OUT=/mnt/us/paperkiosk-diag.txt
{
  echo "== date"; date
  echo "== version"; cat /etc/prettyversion.txt 2>/dev/null; uname -a
  echo "== binaries"; ls /usr/bin /usr/sbin /app/bin 2>/dev/null | grep -i -E "mesquite|chrom|browser|webkit|kindlebrowser|fbink|eips|sqlite"
  echo "== /app"; ls -la /app 2>/dev/null
  echo "== chromium dirs"; ls -d /app/chromium* /usr/lib/chromium* /opt/* 2>/dev/null
  echo "== browser procs"; ps w 2>/dev/null | grep -i -E "browser|chrom|mesquite|webkit|cvm|pillow" | grep -v grep
  echo "== mesquite shared"; ls /var/local/mesquite 2>/dev/null; ls /var/local/mesquite/shared/javascripts 2>/dev/null | head -40
  echo "== /usr/share mesquite"; ls -d /usr/share/*mesquite* /usr/share/webkit* /usr/lib/*webkit* 2>/dev/null
  echo "== appreg browser/store"; sqlite3 /var/local/appreg.db "select * from properties where handlerId like '%browser%' or handlerId like '%store%' or handlerId like '%mesquit%';" 2>&1
  echo "== appreg tables"; sqlite3 /var/local/appreg.db ".tables" 2>&1
  echo "== chromebar"; lipc-probe -v com.lab126.chromebar 2>&1 | head -40
  echo "== browser lipc"; lipc-probe -a 2>/dev/null | grep -i -E "browser|chrom|store|mesquite" | head
  echo "== screen"; eips -i 2>&1 | head -20
  echo "== done"
} > "$OUT" 2>&1
