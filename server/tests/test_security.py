"""Access and injection tests: nothing works without the kiosk key or the admin password, other websites
can't press buttons, risky actions (unlock, open the garage) need allow_risky, and nothing from Home Assistant
or the URL can inject markup.

  cd server && docker run --rm -v ./app:/app:ro -v ./tests:/tests:ro paperkiosk python -m unittest discover -s /tests
"""
import json
import re
import unittest
import urllib.error
import urllib.parse
import urllib.request

import test_kiosk as T
from test_kiosk import KIOSK_KEY, PASSWORD, NoRedirect, auth, config, fake_ha, server, write_cfg

P = '"\'><zq>'


class Security(unittest.TestCase):
    setUpClass = classmethod(T.Kiosk.setUpClass.__func__)
    tearDownClass = classmethod(T.Kiosk.tearDownClass.__func__)
    setUp, get, post = T.Kiosk.setUp, T.Kiosk.get, T.Kiosk.post
    def raw(self, path, data=None, cookie="", headers=None):
        """(status, body, headers) without following redirects."""
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     data=urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None)
        if cookie:
            req.add_header("Cookie", cookie)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        opener = urllib.request.build_opener(NoRedirect)
        try:
            with opener.open(req) as r:
                return r.status, r.read().decode(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(errors="replace"), e.headers

    def kiosk_cookie(self):
        return auth.kiosk_cookie().split(";")[0]

    # --- access -------------------------------------------------------------------------------

    def test_nothing_without_access(self):
        for p in ["/", "/rooms", "/room/living_room", "/device/light.floor_lamp", "/settings", "/x.js?u=/"]:
            status, body, _ = self.raw(p)
            self.assertIn(status, (401, 200), p)
            self.assertNotIn("Floor lamp", body, p)
        self.assertEqual(self.raw("/config")[2]["Location"], "/login")
        self.raw("/x.js?u=/&do=act&a=toggle&e=light.floor_lamp")
        self.raw("/act", {"a": "toggle", "e": "light.floor_lamp", "b": "/"})
        self.raw("/config", {"cat_name": "Hacked"})
        self.assertEqual(fake_ha.CALLS, [])
        self.assertNotEqual(config.get()["cat_name"], "Hacked")
        self.assertEqual(self.raw("/health")[0], 200)

    def test_pairing_with_the_key(self):
        self.assertEqual(self.raw("/?key=wrong")[0], 401)
        status, body, h = self.raw(f"/rooms?key={KIOSK_KEY}&p=2")
        self.assertEqual(status, 200)                                  # the page itself: cookieless screens work
        self.assertIn('history.replaceState(null,"","/rooms?p=2")', body)   # the key leaves the address bar
        self.assertNotIn(KIOSK_KEY, body)
        cookie = h["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertNotIn(KIOSK_KEY, cookie)
        jar = cookie.split(";")[0]
        self.assertEqual(self.raw("/", cookie=jar)[0], 200)
        self.assertEqual(self.raw("/config", cookie=jar)[2]["Location"], "/login")   # the kiosk key isn't the admin
        self.raw("/act", {"a": "toggle", "e": "light.floor_lamp", "b": "/"}, cookie=jar)
        self.assertTrue(fake_ha.CALLS)

    def test_login(self):
        self.assertEqual(self.raw("/login", {"password": "nope"})[0], 401)
        status, _, h = self.raw("/login", {"password": PASSWORD})
        self.assertEqual((status, h["Location"]), (303, "/config"))
        jar = h["Set-Cookie"].split(";")[0]
        self.assertEqual(self.raw("/config", cookie=jar)[0], 200)
        self.assertFalse(auth.is_admin({"pk_admin": "9999999999.forged"}))

    def test_login_is_rate_limited(self):
        auth._fails["10.9.9.9"] = (10, __import__("time").time())
        self.assertTrue(auth.login_blocked("10.9.9.9"))
        auth._fails.clear()

    def test_other_sites_cant_press_buttons(self):
        jar = self.kiosk_cookie()
        evil = [{"Origin": "http://evil.example"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"},
                {"Sec-Fetch-Site": "same-site"}, {"Referer": "http://evil.example/x"}]
        for h in evil:
            self.assertEqual(self.raw("/act", {"a": "toggle", "e": "light.floor_lamp", "b": "/"}, jar, h)[0], 403, h)
            self.assertEqual(self.raw("/x.js?u=/&do=act&a=toggle&e=light.floor_lamp", None, jar, h)[0], 403, h)
        self.assertEqual(fake_ha.CALLS, [])
        host = f"127.0.0.1:{self.port}"
        self.raw("/act", {"a": "toggle", "e": "light.floor_lamp", "b": "/"}, jar, {"Origin": f"http://{host}"})
        self.assertEqual(len(fake_ha.CALLS), 1)

    def test_config_needs_csrf_token(self):
        fields = T.form_fields(self.get("/config")[1])
        self.assertTrue(fields["csrf"][0])
        bad = dict(fields, csrf=["x"], cat_name=["Hacked"])
        self.assertEqual(self.raw("/config", bad, T.ADMIN)[0], 403)
        self.assertNotEqual(config.get()["cat_name"], "Hacked")
        self.assertEqual(self.raw("/config", dict(fields, cat_name=["Pixel"]), T.ADMIN)[0], 303)
        self.assertEqual(config.get()["cat_name"], "Pixel")

    def test_query_strings_are_not_logged(self):
        lines = []
        old = server.Handler.log_message
        server.Handler.log_message = lambda self, fmt, *a: lines.append(fmt % a)
        try:
            self.raw(f"/?key={KIOSK_KEY}")
        finally:
            server.Handler.log_message = old
        self.assertFalse([x for x in lines if KIOSK_KEY in x])

    # --- risky actions ------------------------------------------------------------------------

    def test_unlock_and_garage_need_allow_risky(self):
        self.post("/act", {"a": "unlock", "e": "lock.front_door", "b": "/"})
        self.post("/act", {"a": "open", "e": "cover.garage_door", "b": "/"})
        self.assertEqual(fake_ha.CALLS, [])
        self.post("/act", {"a": "lock", "e": "lock.front_door", "b": "/"})       # locking is always fine
        self.assertEqual(fake_ha.CALLS[-1][:2], ("lock", "lock"))
        _, body = self.get("/room/hall")
        self.assertNotIn('value="unlock"', body)
        write_cfg(known=None, allow_risky=["lock.front_door", "cover.garage_door"])
        self.assertIn('value="unlock"', self.get("/room/hall")[1])
        self.post("/act", {"a": "unlock", "e": "lock.front_door", "b": "/"})
        self.post("/act", {"a": "open", "e": "cover.garage_door", "b": "/"})
        self.assertEqual([c[:2] for c in fake_ha.CALLS[-2:]], [("lock", "unlock"), ("cover", "open_cover")])

    def test_allow_risky_on_config_page(self):
        page = self.get("/config")[1]
        self.assertIn('name="allow_risky" value="lock.front_door"', page)
        fields = T.form_fields(page)
        fields["allow_risky"] = ["lock.front_door", "light.floor_lamp"]
        T.configpage_save(fields)
        self.assertEqual(config.get()["allow_risky"], ["light.floor_lamp", "lock.front_door"])

    # --- injection ----------------------------------------------------------------------------

    def test_no_markup_from_home_assistant_or_settings(self):
        for a in fake_ha.AREAS:
            a["name"] += P
        for s in fake_ha.STATES.values():
            at = s["attributes"]
            at["friendly_name"] = (at.get("friendly_name") or s["entity_id"]) + P
            for k in ("effect_list", "source_list", "options", "hvac_modes", "fan_modes"):
                if k in at:
                    at[k] = [v + P for v in at[k]]
            if s["entity_id"].startswith("media_player"):
                s["state"], at["media_title"], at["source"] = "playing", "song" + P, "src" + P
            if s["entity_id"].startswith("sensor"):
                at["unit_of_measurement"] = "u" + P
        write_cfg(known=None, your_name="you" + P, cat_name="cat" + P, nicknames={"light.floor_lamp": "nick" + P},
                  countdowns=[{"name": "cd" + P, "date": "12-01"}],
                  kiosks=[{"id": "k1", "name": "kn" + P, "ip": "10.0.0.9", "settings": {}}])
        q = urllib.parse.quote
        paths = T.PAGES + ["/config", "/config?kiosk=k1", "/login", "/x.js?u=/"] + \
            [f"/device/{e}" for e in fake_ha.STATES] + [
            "/device/light.shelf_leds?b=" + q('/x"><zq>') + "&p=" + q('1"><zq>'),
            "/x.js?u=" + q('/device/light.shelf_leds?b=/a"><zq>'), "/config?kiosk=" + q('"><zq>')]
        for p in paths:
            status, body, _ = self.raw(p, cookie=T.ADMIN)
            if p.startswith("/x.js"):
                body = json.loads(body[3:body.rindex(",")])
            self.assertNotIn("<zq>", body, p)

    def test_back_links_stay_on_this_site(self):
        for b in ("//evil.example", "http://evil.example", "/x\"y", "javascript:alert(1)"):
            self.assertEqual(server.safe_back(b), "/")
        self.assertEqual(server.safe_back("/room/hall?p=2"), "/room/hall?p=2")


class Screens(unittest.TestCase):
    """screens.py (scripts/add-screen.sh): adding a screen with its own room."""

    def setUp(self):
        fake_ha.reset()
        write_cfg(known=None)

    def test_add_screen_with_its_own_room(self):
        import io
        import contextlib
        import screens
        with contextlib.redirect_stdout(io.StringIO()) as out:
            screens.add("Bedroom Kindle", "10.0.0.7", "bedroom")
            screens.add("Bedroom Kindle", "10.0.0.8")                 # same name, other IP: a new id
            screens.add("Renamed", "10.0.0.7")                        # same IP: renamed, settings kept
        self.assertEqual(out.getvalue().split(), ["bedroom-kindle", "bedroom-kindle-2", "bedroom-kindle"])
        k = config.get()["kiosks"]
        self.assertEqual([(x["id"], x["name"], x["ip"]) for x in k],
                         [("bedroom-kindle", "Renamed", "10.0.0.7"), ("bedroom-kindle-2", "Bedroom Kindle", "10.0.0.8")])
        self.assertEqual(k[0]["settings"]["home_area"], "bedroom")
        cfg = config.effective(config.get(), "bedroom-kindle")
        self.assertEqual(server.home_data(cfg)["room_id"], "bedroom")   # its own room, not the main room's cards
        for bad in (("x", "not-an-ip"), ("x", "10.0.0.9", "Bad Room!")):
            with self.assertRaises(SystemExit):
                screens.add(*bad)


class InstallerOutput(unittest.TestCase):
    """What the installer evals (check_ha.py / screens.py --shell output) can't run commands."""

    def test_shell_assignments_stay_one_line(self):
        import contextlib
        import io
        import shlex
        import check_ha
        evil = "Attic\nHA_PWNED=$(touch /tmp/pwned)\n`id`;'\""
        with contextlib.redirect_stdout(io.StringIO()) as out:
            check_ha.emit({"ok": True, "location": evil, "areas": ["Hall", evil]}, True)
        lines = out.getvalue().splitlines()
        self.assertEqual([x.split("=", 1)[0] for x in lines], ["HA_OK", "HA_LOCATION", "HA_AREAS"])
        for line in lines:   # each value is one complete shell word list: no command substitution survives
            value = line.split("=", 1)[1]
            words = shlex.split(value.strip("()")) if value.startswith("(") else shlex.split(value)
            self.assertTrue(all("\n" not in w for w in words))
        self.assertIn("'Attic HA_PWNED=$(touch /tmp/pwned) `id`;'\"'\"'\"'", lines[1])


class PairingRedirect(unittest.TestCase):
    setUpClass = classmethod(T.Kiosk.setUpClass.__func__)
    tearDownClass = classmethod(T.Kiosk.tearDownClass.__func__)
    setUp = T.Kiosk.setUp
    raw = Security.raw

    def test_pairing_never_redirects_off_site(self):
        for path in ("//evil.example/", "/\\evil.example"):
            status, body, h = self.raw(f"{urllib.parse.quote(path)}?key={KIOSK_KEY}")
            if status == 200:   # served as a page here: the address it puts back is local too
                self.assertNotIn("evil", body.split("replaceState")[-1][:60])
                continue
            self.assertEqual(status, 303)
            loc = h["Location"]   # a path on this site ("/evil.example/" is just a page here), never another host
            self.assertTrue(loc.startswith("/") and not loc.startswith("//") and "\\" not in loc, loc)
