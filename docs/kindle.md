# The Kindle

## Before you start

PaperKiosk runs on a **jailbroken** Kindle with **KUAL** (Kindle Unified Application Launcher). The jailbreak
is the one step nobody can automate for you; the community guide at **https://kindlemodding.org** has the
current method for every model and firmware. Install from there:

1. the jailbreak for your model and firmware,
2. **KUAL** (it shows up as a book in your library),
3. optional but recommended: **USBNetwork**. With it, the PaperKiosk server can reach the Kindle over Wi-Fi to
   start the kiosk for you, update it, and take screenshots.

Tested on a Kindle Paperwhite 3 (7th generation, 1072 × 1448, firmware 5.14). Other touch Kindles on firmware
5.x use the same browser engine and should work; tell us how it goes on yours.

## What the installer puts on it

`/mnt/us/extensions/paperkiosk` (the `extensions` folder you see over USB), a KUAL extension with the menu
**PaperKiosk**:

| Menu item | What it does |
| --- | --- |
| Start kiosk | Registers the fullscreen app, installs the font, keeps the screen on, starts SSH (if set up) and opens the kiosk |
| Stop kiosk | Closes it and lets the Kindle sleep again |
| Enable SSH | Starts USBNetwork's SSH server with PaperKiosk's key (only if you chose SSH in the installer) |
| Diagnostics | Writes `paperkiosk-diag.txt` (system info, for bug reports) |
| Uninstall kiosk app | Removes the app from the Kindle's app registry and the font from fontconfig |

The kiosk is a small **fullscreen app** (a "WAF" app, the same engine as the Kindle's browser, but without its
address bar): `waf/index.html` holds one full-size frame with your kiosk link. It is registered in
`/var/local/appreg.db` (a backup of that file from before the first install is kept as
`appreg.db.bak-paperkiosk` on the Kindle's drive). Nothing on the Kindle's system partition is changed.

Also in the extension: the dashboard font as a system font (`fonts/`, see below), and `bin/nightly.sh`, which
restarts the kiosk app every night at 04:00 while it runs.

With SSH set up, the installer also sets USBNetwork to use **dropbear** with **SSH on Wi-Fi only** (USB drive
mode keeps working). The old USBNetwork config is kept as `usbnet/etc/config.bak-paperkiosk`.

## Living with it

- **Keep it charging.** The screen stays on.
- **After a restart** of the Kindle: *KUAL → PaperKiosk → Start kiosk*.
- **Give it a fixed IP** in your router (and the server too).
- **Downtime hours** (settings page, *Look & layout*): a sleepy page that checks in every 2 minutes, saves battery.
- **Remove it:** *Uninstall kiosk app*, then delete `extensions/paperkiosk` over USB.

## Working on it over SSH (`kindle/tools`)

With SSH set up, from the PaperKiosk folder on the server:

```sh
kindle/tools/shot.sh out.png            # screenshot of the Kindle's screen
kindle/tools/tap.sh 980 1400            # simulate a tap at screen pixel x y
kindle/tools/kiosk-open.sh /weather     # open a page full screen (add out.png: screenshot, then back to Home)
kindle/tools/taptime.sh 267 1390        # how many ms after a tap the screen changed
```

## Things we learned about the Kindle's browser

The Kindle's web engine is **WebKit 534** (Safari 5.1 era). If you change the pages, this is what matters:

- No flexbox, `calc()`, CSS variables or `vh`; JavaScript is ES5. SVGs need `width`/`height` attributes.
- **Don't use `XMLHttpRequest`** in kiosk pages: after one, the Kindle repaints the whole page and taps land
  about a second late. Live updates poll a 1×1 image (`/stamp.gif`); buttons load the next page with a
  `<script>` tag (`/x.js`) and swap only what changed (a full page load takes ~850 ms and flashes).
- **Big rounded boxes are slow to paint.** Big boxes are square with small corner pieces on top; small radii
  (pills, tabs) are fine. Icons are PNGs at the size they are shown (SVG rasterizes slowly).
- **Don't put a CSS transform on the frame** in `waf/index.html`, and don't add `<kindle:gestures>` to the
  app's `config.xml`: both make the app crash on taps.
- After many hours of reloads the browser **loses web-font letters** ("i! ide ar"). That's why the font is
  installed as a system font ("Kiosk Nunito", `bin/fonts.sh`) and the app restarts nightly.
- `Thread-137 ... segfault` lines in `/var/log/messages` when the app starts or stops come from Amazon's Java
  framework and are harmless; `mesquite (...) segfault` means the kiosk app crashed.
