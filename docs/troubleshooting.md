# Troubleshooting

**Start here:** `docker compose logs --tail 50 paperkiosk` (in the PaperKiosk folder) shows what the server saw.

### "This screen isn't paired"
The screen has no valid kiosk cookie. Open the kiosk link once (`./scripts/30-start-server.sh` prints it).
On a KUAL device: run `./scripts/40-kindle-install.sh` again (it writes the link into the app), then *Start kiosk*.
Made a new key with `--new-key`? Then every screen needs this.

### "Oh no! I can't reach Home Assistant"
The message under it says why.
- *No Home Assistant token yet*: run `./scripts/20-home-assistant.sh`.
- *Home Assistant refused the token*: the token was deleted or the user disabled. Make a new one, same script.
- A connection error: is `HA_URL` in `.env` right **from inside the container**? Home Assistant on the same
  machine: `http://host.docker.internal:8123`. `homeassistant.local` often doesn't resolve inside Docker: use
  the IP address. After editing `.env`: `docker compose up -d`.

### The settings page says "Forbidden"
- *The form is out of date*: reload the page (you logged in again in another tab).
- *This request came from another website*: a browser extension or proxy changes the `Origin` header, or you
  opened PaperKiosk under one address and post to another. Use the same address everywhere.

### Forgot the settings password
`./scripts/10-configure.sh --new-password`. It works right away.

### The device doesn't show up during setup
- Same Wi-Fi as the server? Open `http://<server>:8100/health` in the device's browser: it should say `ok`.
- A firewall on the server (`ufw`, `firewalld`) may block port 8100 from the LAN: allow it.
- Check `paperkiosk.log` on the device's drive.

### SSH to the device doesn't work
- SSH only runs after *Start kiosk* or *Enable SSH* (it doesn't survive a restart of the device).
- `Connection refused`: the firewall rule is there, but the SSH server isn't running: *Enable SSH*.
- "Host key changed": you reinstalled USBNetwork or switched between OpenSSH and dropbear. Check that it is
  really your device, then delete `ssh/kindle_known_hosts`.

### The kiosk app crashes on the device (a "Collecting debug info" dialog)
See the last section of [kual.md](kual.md). With SSH: `grep segfault /var/log/messages` on the device.

### Missing letters after many hours
The font isn't installed as a system font: *Start kiosk* runs `bin/fonts.sh`; check `paperkiosk.log`.

### A device isn't on the device
New devices wait under **New in Home Assistant** on the settings page until you tick *Show*. Devices without an
area show under *Other*. Diagnostic and config entities, and hidden or disabled ones, are left out like on
Home Assistant's own dashboards.

### A lock or garage door has no unlock/open button
On purpose: tick *allow unlock/open* for it on the settings page (Devices).

### Windows (WSL + Docker Desktop)
- **"Docker is installed but this user can't use it"**: start Docker Desktop, and turn on its WSL integration for
  your distro (Settings → Resources → WSL integration).
- **Screens can't connect**: allow port 8100 in Windows Firewall for private networks (the install guide has the
  PowerShell command), set your Wi-Fi to *Private*, and check that `PAPERKIOSK_URL` in `.env` uses the PC's own
  IP (`ipconfig` in PowerShell), not WSL's.
- **Screens stop updating at night**: the PC went to sleep. Set sleep to *Never* when plugged in.
- **Every screen shows the main settings**: Docker Desktop hides where screens connect from, so per-screen
  settings (matched by IP) can't work there.
