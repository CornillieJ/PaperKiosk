"""Tests against the pretend Home Assistant (fake_ha.py). Run in the kiosk image:

  cd server && docker run --rm -v ./app:/app:ro -v ./tests:/tests:ro paperkiosk python -m unittest discover -s /tests -v

The crawler test opens every Kindle page, submits every button on it and checks each one reached HA as a
service call (no button silently refused by the server's validation).
"""
import html
import json
import os
import re
import sys
import tempfile
import threading
import unittest
from datetime import datetime
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

tmp = tempfile.mkdtemp()
with open(os.path.join(tmp, "token"), "w") as f:
    f.write("test")
os.environ.update(HA_TOKEN_FILE=os.path.join(tmp, "token"), CONFIG_FILE=os.path.join(tmp, "config.json"),
                  SECRETS_DIR=tmp)
KIOSK_KEY, PASSWORD = "test-kiosk-key-0123456789", "correct horse battery"
sys.path[:0] = ["/app", os.path.dirname(os.path.abspath(__file__))]

import fake_ha  # noqa: E402
import auth  # noqa: E402

with open(os.path.join(tmp, "kiosk_key"), "w") as f:
    f.write(KIOSK_KEY)
with open(os.path.join(tmp, "admin_password"), "w") as f:
    f.write(auth.hash_password(PASSWORD, 1000))
ADMIN = auth.admin_cookie().split(";")[0]     # the tests browse as a logged-in admin unless they say otherwise
urllib.request.install_opener(urllib.request.build_opener())
urllib.request._opener.addheaders = [("Cookie", ADMIN)]
import config  # noqa: E402
import configpage  # noqa: E402
import kawaii  # noqa: E402
import server  # noqa: E402

server.ha = fake_ha.fake_ha
server.time.sleep = lambda s: None
server.Handler.log_message = lambda *a: None

BASE_CFG = {
    "home_area": "living_room",
    "sleep_from": 0, "sleep_to": 0,   # no downtime hours (tests run at any time)
    "home_devices": ["light.sofa", "light.sidebar_leds", "climate.living_room_ac", "media_player.tv"],
    "home_scenes": ["scene.movie_night"],
    "kinds": {"light.sidebar_leds": "strip", "light.christmas": "xmas", "climate.living_room_ac": "ac",
              "media_player.tv": "tv", "switch.sidebar": "strip"},
    "buttons": {"light.sidebar_leds": ["script.sidebar_red", "script.sidebar_rainbow"]},
    "countdowns": [{"name": "Mochi's birthday", "date": "11-20"}],
}
PAGES = ["/", "/rooms", "/room/living_room", "/room/kitchen", "/room/hall", "/room/bedroom", "/lights",
         "/lights/week", "/weather", "/info", "/settings"] + [f"/v/{i}" for i in range(1, 5)]
FORM_RE = re.compile(r'<form method="post" action="(/act|/settings)"[^>]*>(.*?)</form>', re.S)
INPUT_RE = re.compile(r'<input type="hidden" name="([a-z])" value="([^"]*)">')


def write_cfg(**extra):
    config.save({**BASE_CFG, **extra})
    server.registry_cache["at"] = 0
    server.usage_cache.clear()


class Kiosk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def setUp(self):
        fake_ha.reset()
        write_cfg(known=None)

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return r.status, r.read().decode()

    def post(self, path, fields):
        data = urllib.parse.urlencode(fields, doseq=True).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data)
        opener = urllib.request.build_opener(NoRedirect)
        opener.addheaders = [("Cookie", ADMIN)]
        try:
            opener.open(req)
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Location")
        return 200, None

    def device_pages(self):
        _, body = self.get("/room/living_room")
        return sorted(set(html.unescape(m) for m in re.findall(r'href="(/device/[^"]+)"', body)))

    # --- pages ---------------------------------------------------------------------------------

    def test_pages_render(self):
        for p in PAGES + self.device_pages() + ["/config"]:
            status, body = self.get(p)
            self.assertEqual(status, 200, p)
            self.assertNotIn("Traceback", body)
            if p != "/config":
                self.assertNotIn(kawaii.STAMP_MARK, body, p)
                self.assertEqual(body.count('<div class="tab'), 6, p)

    def test_every_button_reaches_home_assistant(self):
        tested = 0
        for p in PAGES + self.device_pages():
            _, body = self.get(p)
            for action, inner in FORM_RE.findall(body):
                fields = {k: html.unescape(v) for k, v in INPUT_RE.findall(inner)}
                if action == "/settings" or fields.get("a") == "alloff":
                    continue
                fake_ha.reset()
                server.registry_cache["at"] = 0
                before = len(fake_ha.CALLS)
                status, where = self.post("/act", fields)
                self.assertEqual(status, 303, (p, fields))
                calls = [c for c in fake_ha.CALLS[before:] if c[0] != "weather"]
                self.assertTrue(calls, f"button on {p} did nothing: {fields}")
                self.assertEqual(where, fields["b"])
                tested += 1
                # the same button the way the page script sends it (JSONP, see kawaii.CLIENT_JS)
                fake_ha.reset()
                server.registry_cache["at"] = 0
                before = len(fake_ha.CALLS)
                _, js = self.get("/x.js?" + urllib.parse.urlencode({"u": fields["b"], "do": "act", **fields}))
                self.assertTrue(js.startswith("hk(") and js.endswith(")"), p)
                html_, url = json.loads("[" + js[3:-1] + "]")
                self.assertEqual(url, fields["b"])
                self.assertIn('<div id="tabs">', html_)
                self.assertTrue([c for c in fake_ha.CALLS[before:] if c[0] != "weather"], f"x.js: {fields}")
        self.assertGreater(tested, 60)

    def test_option_buttons_send_their_value(self):
        self.post("/act", {"a": "source", "e": "media_player.tv", "v": "YouTube", "b": "/"})
        self.assertEqual(fake_ha.STATES["media_player.tv"]["attributes"]["source"], "YouTube")
        self.post("/act", {"a": "mode", "e": "climate.living_room_ac", "v": "heat", "b": "/"})
        self.assertEqual(fake_ha.STATES["climate.living_room_ac"]["state"], "heat")
        self.post("/act", {"a": "color", "e": "light.sidebar_leds", "v": "pink", "b": "/"})
        self.assertEqual(fake_ha.STATES["light.sidebar_leds"]["attributes"]["hs_color"], [325, 75])
        self.post("/act", {"a": "white", "e": "light.kitchen", "v": "warm", "b": "/"})
        self.assertEqual(fake_ha.STATES["light.kitchen"]["attributes"]["color_temp_kelvin"], 2700)

    def test_jsonp_pages_and_settings(self):
        for p in PAGES + ["/nope", "//evil.example/"]:
            _, js = self.get("/x.js?" + urllib.parse.urlencode({"u": p}))
            html_, url = json.loads("[" + js[3:-1] + "]")
            self.assertTrue(url.startswith("/") and not url.startswith("//"), url)
            self.assertIn("<body>", html_)
        self.get("/x.js?" + urllib.parse.urlencode({"u": "/settings", "do": "settings", "k": "live_seconds", "v": "10"}))
        self.assertEqual(config.get()["live_seconds"], 10)

    def test_stamp_gif(self):
        cfg = config.effective(config.get(), "")
        stamp = server.page_stamp(server.page_data("/", cfg)[1], cfg)
        for s_, width in ((stamp, 1), ("old", 2)):
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/stamp.gif?p=/&s={s_}") as r:
                gif = r.read()
            self.assertTrue(gif.startswith(b"GIF89a"))
            self.assertEqual(gif[6], width)

    def test_bad_values_are_refused(self):
        bad = [{"a": "source", "e": "media_player.tv", "v": "Evil"}, {"a": "mode", "e": "climate.living_room_ac", "v": "boil"},
               {"a": "color", "e": "light.sofa", "v": "red"},          # sofa is dimmable only
               {"a": "level", "e": "light.sofa", "v": "55"}, {"a": "toggle", "e": "remote.ir_blaster"},
               {"a": "run", "e": "script.not_a_button"}, {"a": "option", "e": "light.sofa", "v": "x"},
               {"a": "toggle", "e": "light.ball"}]                      # unavailable
        for f in bad:
            before = len(fake_ha.CALLS)
            self.post("/act", {**f, "b": "/"})
            self.assertEqual([c for c in fake_ha.CALLS[before:] if c[1] != "get_forecasts"], [], f)

    def test_extra_buttons_only_when_configured(self):
        # hidden from the rooms: only usable as an extra button on the sidebar's page
        write_cfg(known=None, hidden=["script.sidebar_red"])
        self.post("/act", {"a": "run", "e": "script.sidebar_red", "b": "/"})
        self.assertIn(("script", "turn_on", ("script.sidebar_red",), {}), fake_ha.CALLS)
        write_cfg(known=None, buttons={}, hidden=["script.sidebar_red"])
        before = len(fake_ha.CALLS)
        self.post("/act", {"a": "run", "e": "script.sidebar_red", "b": "/"})
        self.assertEqual([c for c in fake_ha.CALLS[before:] if c[0] == "script"], [])

    def test_all_off_includes_light_kinds(self):
        self.post("/act", {"a": "alloff", "e": "all", "b": "/lights"})
        offs = {(c[0], e) for c in fake_ha.CALLS if c[1] == "turn_off" for e in c[2]}
        self.assertIn(("light", "light.sofa"), offs)
        self.assertIn(("switch", "switch.sidebar"), offs)        # kind "strip" counts as a light
        self.assertNotIn(("media_player", "media_player.tv"), offs)

    # --- features ------------------------------------------------------------------------------

    def test_new_entities_wait_for_approval(self):
        known = [s["entity_id"] for s in fake_ha.BASE if s["entity_id"] != "light.christmas"]
        write_cfg(known=known)
        _, body = self.get("/room/living_room")
        self.assertNotIn("Christmas", body)
        _, page = self.get("/config")
        self.assertIn("New in Home Assistant (1)", page)
        fields = form_fields(page)
        fields["kind:light.christmas"] = ["xmas"]
        fields["nick:light.christmas"] = ["Twinkles"]
        configpage_save(fields)
        self.assertNotIn("light.christmas", config.get()["known"])   # not ticked: still waiting
        fields["show_new"] = ["light.christmas"]
        configpage_save(fields)
        cfg = config.get()
        self.assertIn("light.christmas", cfg["known"])
        self.assertEqual(cfg["kinds"]["light.christmas"], "xmas")
        server.registry_cache["at"] = 0
        _, body = self.get("/room/living_room")
        self.assertIn("Twinkles", body)

    def test_first_run_knows_everything(self):
        write_cfg(known=None)
        self.get("/")
        self.assertIn("light.christmas", config.get()["known"])

    def test_config_roundtrip_keeps_everything(self):
        write_cfg(known=None, nicknames={"light.sofa": "Comfy"}, icons={"area:hall": "door"}, hidden=["light.hall"],
                  indoor_temp="sensor.living_room_temperature", kiosk_area="kitchen")
        self.get("/")
        before = config.get()
        _, page = self.get("/config")
        configpage_save(form_fields(page))
        after = config.get()
        for k in before:
            self.assertEqual(before[k], after[k], k)

    def test_move_kiosk(self):
        self.post("/settings", {"k": "kiosk_area", "v": "kitchen", "b": "/settings"})
        self.assertEqual(config.get()["kiosk_area"], "kitchen")
        _, body = self.get("/")
        self.assertIn("Kitchen", body)
        self.assertNotIn("Air con", body)
        self.post("/settings", {"k": "kiosk_area", "v": "", "b": "/settings"})
        self.assertEqual(config.get()["kiosk_area"], "")

    def test_home_layouts(self):
        pool = ["light.sofa", "light.sidebar_leds", "climate.living_room_ac", "media_player.tv", "light.christmas",
                "switch.sidebar"]
        for n in range(0, 7):
            write_cfg(known=None, home_devices=pool[:n])
            _, body = self.get("/")
            self.assertEqual(body.count('class="card '), n if n else 4, n)   # 0 = the room's devices automatically
            if n > 4:
                self.assertIn("sm xs", body)

    def test_bins_tomorrow(self):
        _, body = self.get("/")
        self.assertIn('<b>GFT + PMD</b> tomorrow', body)             # both bins due tomorrow, nothing later
        self.assertNotIn("Restafval", body)
        fake_ha.bins({"pmd": 0, "gft": 7})                           # collected today: not tomorrow
        _, body = self.get("/")
        self.assertIn('class="abs bins none"', body)
        for e in [e for e in fake_ha.STATES if "afvalbeheer" in e]:  # no bin calendar: no pill at all
            del fake_ha.STATES[e]
        _, body = self.get("/")
        self.assertNotIn("bins", body.split("</style>")[-1])

    def test_climate_mode_icon_and_room_temperature(self):
        d = server.home_data(config.get())
        ac = next(x for x in d["devices"] if x["eid"] == "climate.living_room_ac")
        self.assertEqual(ac["mode_icon"], "snowflake")
        del fake_ha.STATES["sensor.living_room_temperature"]          # no thermometer: the airco's reading
        rooms = server.rooms_data(config.get())["rooms"]
        living = next(r for r in rooms if r["id"] == "living_room")
        self.assertEqual((living["temp"], living["climate"]), ("24.5", "snowflake"))

    # --- look & layout, screens -----------------------------------------------------------------

    def test_screen_by_ip_has_its_own_settings(self):
        write_cfg(kiosks=[{"id": "bed", "name": "Bedroom Kindle", "ip": "127.0.0.1",
                           "settings": {"mascot": "dog", "home_devices": ["light.sofa"], "tabs": ["rooms"]}}])
        _, body = self.get("/")
        self.assertEqual(body.count('class="card '), 1)
        self.assertEqual(body.count('<div class="tab'), 2)                # Home + Rooms
        self.assertNotIn("(=", body)                                     # dog faces, not cat ones
        self.assertEqual(config.get()["mascot"], "cat")                  # the main settings are untouched
        self.post("/settings", {"k": "home_style", "v": "2", "b": "/settings"})
        cfg = config.get()
        self.assertEqual((cfg["home_style"], cfg["kiosks"][0]["settings"]["home_style"]), (5, 2))

    def test_config_page_edits_one_screen(self):
        write_cfg(kiosks=[{"id": "bed", "name": "Bedroom Kindle", "ip": "10.0.0.9", "settings": {}}])
        _, page = self.get("/config?kiosk=bed")
        self.assertIn("this screen", page)
        fields = form_fields(page)
        fields["mascot"], fields["nick:light.sofa"] = ["owl"], ["Comfy"]
        configpage_save(fields)
        cfg = config.get()
        self.assertEqual(cfg["mascot"], "cat")
        self.assertEqual(cfg["kiosks"][0]["settings"], {"mascot": "owl"})
        self.assertEqual(cfg["nicknames"]["light.sofa"], "Comfy")       # names are shared by all screens
        fields = form_fields(self.get("/config?kiosk=bed")[1])          # back to the main value: follows it again
        fields["mascot"] = ["cat"]
        configpage_save(fields)
        self.assertEqual(config.get()["kiosks"][0]["settings"], {})

    def test_add_and_remove_screen(self):
        fields = form_fields(self.get("/config")[1])
        fields.update(new_kname=["Bedroom Kindle"], new_kip=["192.168.1.50"])
        configpage_save(fields)
        self.assertEqual([(k["id"], k["ip"]) for k in config.get()["kiosks"]], [("bedroom-kindle", "192.168.1.50")])
        fields = form_fields(self.get("/config")[1])
        fields["kdel"] = ["bedroom-kindle"]
        configpage_save(fields)
        self.assertEqual(config.get()["kiosks"], [])

    def test_brightness_slider(self):
        write_cfg(level_style="slider")
        _, body = self.get("/")
        self.assertIn('class="hearts slider"', body)
        _, body = self.get("/device/light.sidebar_leds")
        self.assertIn("dslider", body)
        fake_ha.CALLS.clear()
        self.post("/act", {"a": "level", "e": "light.sofa", "v": "30", "b": "/"})
        self.assertEqual(fake_ha.CALLS[-1][3], {"brightness_pct": 30})

    def test_home_without_extras(self):
        write_cfg(hello_size="off", home_parts=[], clock_24h=False)
        _, body = self.get("/")
        for part in ('class="abs hello', 'class="abs stick', 'class="abs bins', 'class="abs foot', '<span class="in">'):
            self.assertNotIn(part, body)
        self.assertNotRegex(body, r'class="clk">(1[3-9]|2[0-3]):')       # 12-hour clock

    def test_downtime(self):
        write_cfg(sleep_from=0, sleep_to=0)                              # no downtime hours
        self.assertNotIn("fast asleep", self.get("/")[1])
        self.post("/settings", {"k": "sleep", "v": "bed", "b": "/"})       # Going to bed
        for page in ("/", "/rooms", "/device/light.sofa"):
            body = self.get(page)[1]
            self.assertIn("fast asleep", body)
            self.assertNotIn('id="tabs"', body)
        self.assertIn("PaperKiosk settings", self.get("/config")[1])      # the PC page never sleeps
        self.post("/settings", {"k": "sleep", "v": "wake", "b": "/"})      # Wake up
        self.assertNotIn("fast asleep", self.get("/")[1])
        now = datetime.now().astimezone()
        write_cfg(sleep_from=now.hour, sleep_to=(now.hour + 2) % 24)       # inside the downtime hours
        self.assertIn("fast asleep", self.get("/")[1])
        self.post("/settings", {"k": "sleep", "v": "wake", "b": "/"})      # awake for the rest of the night
        self.assertNotIn("fast asleep", self.get("/")[1])

    def test_festive_and_indoor(self):
        _, body = self.get("/")
        self.assertIn("21.4°", body)          # indoor temperature found automatically
        self.assertTrue(server.home_data(config.get())["festive"])   # Christmas lights (kind xmas) are on

    def test_usage_ranking(self):
        d = server.lights_data(config.get(), 7)
        self.assertTrue(d["usage"]["ok"])
        pcts = [x["pct"] for x in d["usage"]["rank"]]
        self.assertEqual(pcts, sorted(pcts, reverse=True))
        self.assertLessEqual(len(pcts), 5)

    def test_stamp_ignores_drifting_numbers(self):
        a = server.stamp_of(server.page_data("/", config.get())[1])
        fake_ha.STATES["sensor.living_room_temperature"]["state"] = "22.9"
        fake_ha.STATES["climate.living_room_ac"]["attributes"]["current_temperature"] = 24.5
        b = server.stamp_of(server.page_data("/", config.get())[1])
        self.assertEqual(a, b)
        fake_ha.STATES["light.sofa"]["state"] = "off"
        c = server.stamp_of(server.page_data("/", config.get())[1])
        self.assertNotEqual(a, c)

    def test_countdowns_parse(self):
        self.assertEqual(configpage.parse_countdowns("Mochi = 20/11\nbad line\nMum = 3-2"),
                         [{"name": "Mochi", "date": "11-20"}, {"name": "Mum", "date": "02-03"}])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def form_fields(page):
    """The /config form as a browser would submit it (defaults, selected options, checked boxes)."""
    form = page[page.index('<form method="post" action="/config"'):page.index("</form>")]
    fields = {}
    for m in re.finditer(r'<input type="(text|hidden|checkbox|radio)" name="([^"]+)" value="([^"]*)"([^>]*)>', form):
        typ, name, value, rest = m.groups()
        if typ in ("checkbox", "radio") and "checked" not in rest:
            continue
        fields.setdefault(html.unescape(name), []).append(html.unescape(value))
    for m in re.finditer(r'<select( multiple size="\d+")? name="([^"]+)">(.*?)</select>', form, re.S):
        multiple, name, opts = m.groups()
        chosen = re.findall(r'<option value="([^"]*)" selected>', opts)
        if not chosen and not multiple:
            first = re.search(r'<option value="([^"]*)"', opts)
            chosen = [first.group(1)] if first else []
        fields.setdefault(html.unescape(name), []).extend(html.unescape(c) for c in chosen)
    t = re.search(r'<textarea name="countdowns"[^>]*>(.*?)</textarea>', form, re.S)
    fields["countdowns"] = [html.unescape(t.group(1))]
    return fields


def configpage_save(fields):
    config.save(configpage.parse(fields, config.get())[0])
    server.registry_cache["at"] = 0


if __name__ == "__main__":
    unittest.main()
