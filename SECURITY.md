# Security

PaperKiosk can switch things in your home, so it is locked down by default. This page says how, and what is
up to you.

## What PaperKiosk does

- **No access without pairing.** A screen opens the kiosk once with the kiosk link (`/?key=...`, made by the
  installer). It then gets a cookie and stays paired. Without it: no pages, no buttons, nothing from Home
  Assistant. The key is 256 random bits in `secrets/kiosk_key`. A new key (`./scripts/10-configure.sh --new-key`)
  un-pairs every screen.
- **The settings page needs a password** (stored as a PBKDF2-SHA256 hash in `secrets/admin_password`). Wrong
  passwords are slowed down, and after 10 in 15 minutes that address has to wait.
- **Other websites can't use it.** Cookies are `HttpOnly` and `SameSite=Strict`. Button presses and form posts
  must come from PaperKiosk itself (checked with `Origin`, `Referer` and `Sec-Fetch-Site`), and the settings form
  carries a CSRF token. A web page you visit can't switch your lights or read your home's state through your
  browser.
- **Only what the screen shows can be pressed**, with values checked against what the device itself offers
  (no arbitrary Home Assistant service calls).
- **Unlocking locks and opening garage doors and gates is off** until you tick *allow unlock/open* for that
  device on the settings page: anyone standing at a wall screen could use it. Locking and closing always work.
- **The Home Assistant token stays on the server** (`secrets/ha_token`, readable only by you); the screen never
  sees it.
- **The container is locked down:** it runs as your user (not root) with a read-only file system, no Linux
  capabilities, `no-new-privileges`, and memory and process limits. Secrets are mounted read-only.
- Everything that comes from Home Assistant (names, track titles, TV sources, ...) is HTML-escaped, and
  links in URLs are checked; the tests try to inject markup on every page.
- The kiosk key is never written to the log (query strings are left out of it).

## What you should do

- **Keep PaperKiosk on your home network.** Don't forward its port (8100) in your router. It speaks plain HTTP,
  made for old e-ink browsers. To use it from outside, use a VPN (WireGuard, Tailscale, ...), not a port forward.
- **Give it its own Home Assistant user without admin rights.** The installer explains how. Then even a stolen
  token can't change Home Assistant itself.
- **Treat the kiosk link like a house key.** Whoever has it can use the kiosk from your network.
- **Kindle SSH:** with USBNetwork, the Kindle runs an SSH server on Wi-Fi. PaperKiosk logs in with its own key
  (`secrets/kindle_ed25519`), but USBNetwork also accepts the Kindle's root password, which is often derived
  from the serial number. Only use this on a network you trust, or skip SSH in the installer (you then tap
  *Start kiosk* yourself).
- Physical access to the Kindle (USB) gives the kiosk link (it's in the app's files). Anyone who can take the
  Kindle off the wall can already press its buttons.
- Keep it updated: `./scripts/update.sh`.

## Reporting a problem

Found a security issue? Please don't open a public issue. Use GitHub's
[private vulnerability reporting](https://github.com/CornillieJ/PaperKiosk/security/advisories/new) for this
repository. You'll get an answer within a week.
