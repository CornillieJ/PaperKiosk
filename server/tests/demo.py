"""Demo server: the kiosk against the pretend Home Assistant (fake_ha.py), for screenshots and tap tests
without switching anything in a real house. Runs in the PaperKiosk image (from server/):

  docker run --rm -d --name pk-demo -p 8101:8080 -v ./app:/app:ro -v ./tests:/tests:ro \\
      paperkiosk python -u /tests/demo.py [--devices N] [--fresh] [--set key=<json> ...]

Open http://localhost:8101/?key=demo (kiosk) or http://localhost:8101/config (password: demo-password).
Config lives in /tmp inside the container.
"""
import json
import os
import sys
import tempfile

tmp = tempfile.mkdtemp()
with open(os.path.join(tmp, "token"), "w") as f:
    f.write("demo")
os.environ.update(HA_TOKEN_FILE=os.path.join(tmp, "token"), CONFIG_FILE=os.path.join(tmp, "config.json"),
                  SECRETS_DIR=tmp)
sys.path[:0] = ["/app"]
import auth  # noqa: E402

with open(os.path.join(tmp, "kiosk_key"), "w") as f:
    f.write("demo")
with open(os.path.join(tmp, "admin_password"), "w") as f:
    f.write(auth.hash_password("demo-password", 1000))
sys.path[:0] = ["/app", os.path.dirname(os.path.abspath(__file__))]

import fake_ha  # noqa: E402

DEMO_CONFIG = {
    "home_area": "living_room",
    "home_devices": ["light.floor_lamp", "light.shelf_leds", "climate.living_room_ac", "media_player.tv"],
    "home_scenes": ["scene.movie_night"],
    "kinds": {"switch.string_lights": "plug", "light.shelf_leds": "strip", "light.tree_lights": "xmas",
              "climate.living_room_ac": "ac", "media_player.tv": "tv"},
    "nicknames": {"climate.living_room_ac": "Air con"},
    "buttons": {"light.shelf_leds": ["script.shelf_red", "script.shelf_rainbow"]},
    "countdowns": [{"name": "Mochi's birthday", "date": "11-20"}],
    "sleep_from": 0, "sleep_to": 0,
    "your_name": "Sam",
    # everything known except the Christmas lights: they show as "new" on /config
    "known": [s["entity_id"] for s in fake_ha.BASE if s["entity_id"] != "light.tree_lights"],
}

if "--devices" in sys.argv:
    n = int(sys.argv[sys.argv.index("--devices") + 1])
    pool = ["light.floor_lamp", "light.shelf_leds", "climate.living_room_ac", "media_player.tv", "light.tree_lights",
            "switch.string_lights"]
    DEMO_CONFIG["home_devices"] = pool[:n]
    DEMO_CONFIG["known"] = None
for i, arg in enumerate(sys.argv):   # --set key=<json>: change one setting, e.g. --set mascot='"bunny"'
    if arg == "--set":
        key, _, val = sys.argv[i + 1].partition("=")
        DEMO_CONFIG[key] = json.loads(val)
for _e in [e for e in fake_ha.STATES if "afvalbeheer" in e]:   # English bin names in the demo
    del fake_ha.STATES[_e]
fake_ha.bins({"paper": 1, "plastic": 1, "general": 6, "glass": 13})
if "--fresh" not in sys.argv:
    with open(os.environ["CONFIG_FILE"], "w") as f:
        json.dump(DEMO_CONFIG, f)

import server  # noqa: E402

server.ha = fake_ha.fake_ha

if __name__ == "__main__":
    from http.server import ThreadingHTTPServer
    print("demo kiosk on :8080 (fake Home Assistant)", flush=True)
    ThreadingHTTPServer(("", 8080), server.Handler).serve_forever()
