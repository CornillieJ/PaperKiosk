# KUAL devices

PaperKiosk includes a **KUAL extension**: a menu for KUAL (the "Kindle Unified Application Launcher") that runs
the kiosk full screen. This page is about that extension. Anything without KUAL can use the kiosk link instead
(a browser, or another e-paper dashboard): see the README.

## What PaperKiosk does not cover

PaperKiosk starts where KUAL already runs. It does not explain, provide or support jailbreaks or any other way
of getting KUAL onto a device, and it doesn't ask you to modify anything. Which device you run it on is up to
you. If you look into that elsewhere, you do so at your own risk: it can void warranties, break devices, and
isn't legal everywhere.

The extension was developed on a device with a 1072 × 1448 screen, firmware 5.x and the mesquite web engine
(WebKit 534). Other devices running KUAL may differ.

## What the installer puts on the device

`extensions/paperkiosk` (on the drive the device shows over USB; `/mnt/us/extensions/paperkiosk` on the device),
with the KUAL menu **PaperKiosk**:

| Menu item | What it does |
| --- | --- |
| Start kiosk | Registers the fullscreen app, installs the font, keeps the screen on, starts SSH (if set up) and opens the kiosk |
| Stop kiosk | Closes it and lets the device sleep again |
| Enable SSH | Starts USBNetwork's SSH server with PaperKiosk's key (only if you chose SSH in the installer) |
| Diagnostics | Writes `paperkiosk-diag.txt` (system info, for bug reports) |
| Uninstall kiosk app | Removes the app from the app registry and the font from fontconfig |

The kiosk is a small **fullscreen app** (a "WAF" app: the same engine as the built-in browser, without its
address bar). `waf/index.html` holds one full-size frame with your kiosk link. It is registered in
`/var/local/appreg.db`; a backup of that file from before the first install is kept as `appreg.db.bak-paperkiosk`
on the drive. Nothing on the system partition is changed.

Also in the extension: the dashboard font as a system font (`fonts/`, see below), and `bin/nightly.sh`, which
restarts the kiosk app every night at 04:00 while it runs.

**Optional: SSH.** If the device has the **USBNetwork** extension, the installer can set it to **dropbear** with
**SSH on Wi-Fi only** (USB drive mode keeps working) and give this server its own key (`ssh/kindle_ed25519`). Then
the installer starts the kiosk for you, and updates and screenshots work over Wi-Fi. The old USBNetwork config
is kept as `usbnet/etc/config.bak-paperkiosk`. Without SSH you tap *Start kiosk* yourself.

## More than one device

`./install.sh --add-screen`: the same install and start steps, plus its own room and cards if you want. Every
device is saved by name (the first in `.env`, more in `data/kindles.tsv`). With more than one, `kindle/tools`
and steps 4-5 ask which one (the first is preselected), and `scripts/update.sh` updates every device it can
reach. Choose ahead with the name: `KINDLE="Bedroom screen" kindle/tools/shot.sh` (without a terminal, the
first device is used).

## Living with it

- **Keep it charging.** The screen stays on.
- **After a restart** of the device: *KUAL → PaperKiosk → Start kiosk*.
- **Give it a fixed IP** in your router (and the server too).
- **Downtime hours** (settings page, *Look & layout*): a sleepy page that checks in every 2 minutes.
- **Remove it:** *Uninstall kiosk app*, then delete `extensions/paperkiosk` over USB.

## Working on it over SSH (`kindle/tools`)

With SSH set up, from the PaperKiosk folder on the server:

```sh
kindle/tools/shot.sh out.png            # screenshot of the screen
kindle/tools/tap.sh 980 1400            # simulate a tap at screen pixel x y
kindle/tools/kiosk-open.sh /weather     # open a page full screen (add out.png: screenshot, then back to Home)
kindle/tools/taptime.sh 267 1390        # how many ms after a tap the screen changed
```

## Notes on the web engine (WebKit 534)

If you change the pages, this is what matters on these devices:

- No flexbox, `calc()`, CSS variables or `vh`; JavaScript is ES5. SVGs need `width`/`height` attributes.
- **Don't use `XMLHttpRequest`** in kiosk pages: after one, the device repaints the whole page and taps land
  about a second late. Live updates poll a 1×1 image (`/stamp.gif`); buttons load the next page with a
  `<script>` tag (`/x.js`) and swap only what changed (a full page load takes ~850 ms and flashes).
- **Big rounded boxes are slow to paint.** Big boxes are square with small corner pieces on top; small radii
  (pills, tabs) are fine. Icons are PNGs at the size they are shown (SVG rasterizes slowly).
- **Don't put a CSS transform on the frame** in `waf/index.html`, and don't add `<kindle:gestures>` to the
  app's `config.xml`: both make the app crash on taps.
- After many hours of reloads the engine **loses web-font letters** ("i! ide ar"). That's why the font is
  installed as a system font ("Kiosk Nunito", `bin/fonts.sh`) and the app restarts nightly.
- `Thread-137 ... segfault` lines in `/var/log/messages` when the app starts or stops come from the system's
  Java framework and are harmless; `mesquite (...) segfault` means the kiosk app crashed.
