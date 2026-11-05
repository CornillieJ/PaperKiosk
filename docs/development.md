# Development

## How it is built

One small Python server (standard library + `websockets`), no frameworks, no build step. Pages are rendered on
the server as plain HTML that a 2011 browser can draw.

| File | What's in it |
| --- | --- |
| `server/app/server.py` | Home Assistant over its websocket API (registries cached 60 s, states fresh every request, forecasts 10 min, history 5 min), the data per page, action validation, HTTP |
| `server/app/auth.py` | Kiosk key and cookie, password, CSRF token, same-site checks |
| `server/app/kawaii.py` | Every kiosk page in the Kawaii theme, the live-update script |
| `server/app/views.py` | The other home styles (Cozy, Bubbles, Sky, Paper) |
| `server/app/configpage.py` | The settings page and the login page |
| `server/app/config.py` | `data/config.json`: defaults, validation (`clean()`), per-screen settings |
| `server/app/kinds.py`, `pets.py`, `fun.py` | Device kinds and colour presets, the mascots, the Info tab |
| `server/app/check_ha.py` | Connection check for the installer |
| `server/app/screens.py` | Adds a screen with its own settings, for `scripts/add-screen.sh` |

Rules the server keeps:
- Every value from Home Assistant or the user goes through `esc()` before it's in HTML.
- Only actions in `ACTIONS` on entities currently shown are accepted, with values from the entity's own lists
  (`valid_value`); unlock/open only with `allow_risky`.
- Pages stay one screen, ES5, no XHR (see [kual.md](kual.md)).

## Tests

```sh
cd server
docker build -t paperkiosk .
docker run --rm -v ./app:/app:ro -v ./tests:/tests:ro paperkiosk python -m unittest discover -s /tests -v
```

`tests/fake_ha.py` is a pretend Home Assistant (lights, an LED strip, Christmas lights, an AC, a TV, a lock, a
garage door, sensors, weather). `test_kiosk.py` renders every page and presses every button on it (each must
reach HA); `test_security.py` checks pairing, login, CSRF, other-site requests, risky actions and tries to
inject markup everywhere.

## Demo server

The kiosk against the pretend Home Assistant, safe to tap around in:

```sh
cd server
docker run --rm -d --name pk-demo -p 8101:8080 -v ./app:/app:ro -v ./tests:/tests:ro paperkiosk python -u /tests/demo.py
# kiosk: http://localhost:8101/?key=demo     settings: http://localhost:8101/config (password: demo-password)
tests/shots.sh /tmp/shots                    # screenshots at the device's size (headless Chrome)
docker rm -f pk-demo
```

Change something in `app/`, restart the demo, look. Then check on a real KUAL device (`kindle/tools/kiosk-open.sh`):
desktop browsers don't show the old-WebKit problems.
