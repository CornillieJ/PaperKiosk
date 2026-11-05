# kindle/

- `extension/`: the KUAL extension, copied to `/mnt/us/extensions/paperkiosk` by `scripts/40-kindle-install.sh`
  (which fills in the kiosk link in `waf/index.html` and, with SSH, `authorized_keys`).
  - `bin/start.sh` Start kiosk, `bin/stop.sh` Stop kiosk, `bin/ssh.sh` Enable SSH, `bin/diag.sh` Diagnostics,
    `bin/register.sh` / `bin/unregister.sh` the app registry entry (`com.github.paperkiosk`), `bin/fonts.sh` the
    system font, `bin/nightly.sh` the 04:00 restart.
  - `waf/`: the fullscreen app (one frame with the kiosk link).
  - `fonts/`: Nunito as "Kiosk Nunito" (SIL OFL 1.1, `fonts/OFL.txt`).
- `tools/`: helpers for working on the Kindle over SSH from the server (see [docs/kindle.md](../docs/kindle.md)).

FAT file system on the Kindle: scripts need no exec bits; KUAL runs them with the extension folder as cwd.
