"""PaperKiosk settings: /config/config.json (data/config.json next to docker-compose.yml on the host).

Edited from a PC browser at /config, from the Kindle's Settings tab (home style, refresh, move kiosk) or by hand.
Missing keys fall back to DEFAULTS; unknown keys are ignored. Saved atomically; re-read when the file
changes, so hand edits apply on the next page load.

More than one kiosk: "kiosks" lists them ({id, name, ip, settings}). A kiosk is recognised by its IP address
(or, for the preview on /config, the hk_as cookie); its "settings" override the KIOSK_KEYS of the main settings,
everything else (names, icons, hidden devices, ...) is shared. Screens that aren't listed use the main settings.
"""
import json
import os
import re
import threading
from pathlib import Path

PATH = Path(os.environ.get("CONFIG_FILE", "/config/config.json"))

DEFAULTS = {
    "home_area": os.environ.get("HOME_AREA", ""),       # the main room (where the kiosk normally hangs)
    "kiosk_area": "",            # where the kiosk hangs right now (Settings > Move kiosk); "" = home_area
    "home_style": 5,             # 5 Kawaii; 1 Cozy, 2 Bubbles, 3 Sky, 4 Paper (Settings > Home style)
    "home_devices": [],          # entity ids on Home, in order (max 6); empty = lights + switches of home_area
    "home_scenes": [],           # scene/script entity ids shown as buttons on Home (max 3)
    "cat_name": "Mochi",         # the Kawaii cat
    "your_name": "",             # used in greetings ("Good morning, ...")
    "live_seconds": 5,           # how often a page asks if anything changed (reloads only then; 0 = off)
    "refresh_seconds": 600,      # full reload anyway (clears e-ink ghosting; every reload flashes; 0 = off)
    "show_unavailable": True,    # show devices HA reports as unavailable
    "weather_entity": "",        # empty = first weather entity in HA
    "nicknames": {},             # entity id -> display name
    "icons": {},                 # entity id or "area:<area_id>" -> mdi icon name (without "mdi:")
    "kinds": {},                 # entity id -> kind (kinds.KINDS: lamp, strip, xmas, tv, ac, ...): icon, cute extras
    "buttons": {},               # entity id -> scene/script/button ids shown on its detail page (max 8), e.g. colours
    "indoor_temp": "",           # temperature sensor for "inside" on Home; "" = first one in the kiosk's room
    "indoor_humidity": "",       # humidity sensor shown next to it; "" = first one in the kiosk's room
    "approve_new": True,         # new entities in HA stay hidden until they are approved on /config
    "known": None,               # entities seen on /config (None until the first run fills it)
    "seasonal": True,            # snow in December, a pumpkin at Halloween, ...
    "countdowns": [],            # [{"name": "Mochi's birthday", "date": "05-12"}] (MM-DD) on the Info tab
    "allow_risky": [],           # locks / garage doors / gates the kiosk may unlock or open (off by default)
    "hidden": [],                # entity ids not shown anywhere
    "hidden_areas": [],          # area ids not shown on Rooms
    "area_order": [],            # area ids, shown first in this order on Rooms
    # look & layout
    "mascot": "cat",             # the pet on Home (MASCOTS); cat_name is its name
    "level_style": "icons",      # brightness on cards: "icons" (5 hearts/stars/...) or "slider" (10 steps)
    "level_icon": "heart",       # LEVEL_ICONS
    "clock_24h": True,
    "home_parts": ["weather", "bins", "indoor", "moon"],   # what Home shows besides the pet and the cards
    "hello_size": "auto",        # the pet's box on Home: auto (smaller with more cards), large, medium, small, off
    "tabs": ["rooms", "lights", "weather", "info", "settings"],   # tabs next to Home, in this order
    "idle_home": 300,            # seconds without a tap on another tab, then back to Home (0 = stay)
    "kiosks": [],                # [{"id", "name", "ip", "settings": {KIOSK_KEYS overrides}}]
    "sleep_from": 1,             # downtime from this hour ... (sleepy screen, few checks: saves battery)
    "sleep_to": 7,               # ... until this hour; the same hour twice = no downtime
    "sleep_state": {},           # kiosk id ("" = main) -> {"until": ts asleep ("Going to bed"), "awake_until": ts}
}

# Settings each kiosk can have its own value for (the rest is shared by all kiosks)
KIOSK_KEYS = ("home_area", "kiosk_area", "home_style", "home_devices", "home_scenes", "cat_name", "mascot",
              "live_seconds", "refresh_seconds", "indoor_temp", "indoor_humidity", "seasonal", "level_style",
              "level_icon", "clock_24h", "home_parts", "hello_size", "tabs", "idle_home", "weather_entity",
              "sleep_from", "sleep_to")
MASCOTS = ("cat", "dog", "bunny", "bear", "panda", "penguin", "owl", "duck", "unicorn", "koala", "piggy", "robot")
LEVEL_ICONS = ("heart", "star", "paw", "flower", "circle", "lightbulb", "drop")
HOME_PARTS = ("weather", "bins", "indoor", "moon")
HELLO_SIZES = ("auto", "large", "medium", "small", "off")
TAB_KEYS = ("rooms", "lights", "weather", "info", "settings")
IDLE_CHOICES = (0, 60, 120, 300, 600, 1800)
IP_RE = re.compile(r"^[0-9a-fA-F:.]{3,45}$")
KIOSK_ID_RE = re.compile(r"^[a-z0-9-]{1,30}$")

ENTITY_RE = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")
AREA_RE = re.compile(r"^[a-z0-9_]+$")
ICON_RE = re.compile(r"^[a-z0-9-]{1,64}$")
KINDS = ("lamp", "floor", "ceiling", "desk", "strip", "xmas", "tree", "tv", "ac", "heater", "fan", "speaker",
         "purifier", "coffee", "plug")
DATE_RE = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
REFRESH_CHOICES = (0, 30, 60, 120, 300, 600, 1800)
LIVE_CHOICES = (0, 3, 5, 10, 30)

_lock = threading.Lock()
_cache = {"mtime": None, "data": dict(DEFAULTS)}


def get():
    """Current settings (defaults merged with the file)."""
    with _lock:
        try:
            mtime = PATH.stat().st_mtime
        except FileNotFoundError:
            return dict(DEFAULTS)
        if mtime != _cache["mtime"]:
            try:
                raw = json.loads(PATH.read_text())
                _cache["data"] = clean({**DEFAULTS, **{k: v for k, v in raw.items() if k in DEFAULTS}})
            except (ValueError, OSError) as exc:
                print(f"config: ignoring broken {PATH}: {exc}", flush=True)
                _cache["data"] = dict(DEFAULTS)
            _cache["mtime"] = mtime
        return dict(_cache["data"])


def save(data):
    data = clean({**DEFAULTS, **data})
    with _lock:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        tmp.replace(PATH)
        _cache["mtime"] = None
    return data


def update(**changes):
    return save({**get(), **changes})


def update_kiosk(kiosk_id, **changes):
    """Change settings for one kiosk (its overrides), or the main settings when kiosk_id is empty/unknown."""
    data = get()
    k = next((k for k in data["kiosks"] if k["id"] == kiosk_id), None)
    if not k:
        return save({**data, **changes})
    k["settings"] = own_settings(data, {**effective(data, kiosk_id), **changes})
    return save(data)


def own_settings(base, values):
    """The KIOSK_KEYS of values that differ from the main settings (what a kiosk stores)."""
    merged = clean({**base, **{k: v for k, v in values.items() if k in KIOSK_KEYS}})
    return {k: merged[k] for k in KIOSK_KEYS if merged[k] != base[k]}


def effective(cfg, kiosk_id):
    """The settings one kiosk sees: the main settings with its own on top. Adds "kiosk" (id, "" = main)."""
    k = next((k for k in cfg["kiosks"] if k["id"] == kiosk_id), None)
    if not k:
        return {**cfg, "kiosk": "", "kiosk_name": ""}
    return {**clean({**cfg, **k["settings"]}), "kiosk": k["id"], "kiosk_name": k["name"]}


def kiosk_for(cfg, ip, cookie=""):
    """Which kiosk is asking: the hk_as cookie (the /config preview; "-" = main), else its IP address."""
    if cookie:
        return cookie if any(k["id"] == cookie for k in cfg["kiosks"]) else ""
    return next((k["id"] for k in cfg["kiosks"] if k["ip"] == ip), "")


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] or "kiosk"


def _str(v, n=40):
    return str(v or "").strip()[:n]


def clean(d):
    """Validate types and values, dropping anything malformed."""
    out = dict(DEFAULTS)
    out["home_area"] = _str(d.get("home_area"), 64) if AREA_RE.match(_str(d.get("home_area"), 64)) else DEFAULTS["home_area"]
    try:
        out["home_style"] = min(5, max(1, int(d.get("home_style", 5))))
    except (TypeError, ValueError):
        pass
    ka = _str(d.get("kiosk_area"), 64)
    out["kiosk_area"] = ka if AREA_RE.match(ka) and ka != out["home_area"] else ""
    out["home_devices"] = [e for e in d.get("home_devices") or [] if isinstance(e, str) and ENTITY_RE.match(e)][:6]
    out["home_scenes"] = [e for e in d.get("home_scenes") or [] if isinstance(e, str) and ENTITY_RE.match(e)][:3]
    out["cat_name"] = _str(d.get("cat_name"), 20) or DEFAULTS["cat_name"]
    out["your_name"] = _str(d.get("your_name"), 20)
    try:
        r = int(d.get("refresh_seconds", 60))
        out["refresh_seconds"] = r if r in REFRESH_CHOICES else 600
    except (TypeError, ValueError):
        pass
    try:
        lv = int(d.get("live_seconds", 5))
        out["live_seconds"] = lv if lv in LIVE_CHOICES else 5
    except (TypeError, ValueError):
        pass
    out["show_unavailable"] = bool(d.get("show_unavailable", True))
    we = _str(d.get("weather_entity"), 80)
    out["weather_entity"] = we if we.startswith("weather.") and ENTITY_RE.match(we) else ""
    out["nicknames"] = {k: _str(v, 30) for k, v in (d.get("nicknames") or {}).items()
                        if isinstance(k, str) and ENTITY_RE.match(k) and _str(v, 30)}
    out["icons"] = {k: _str(v, 64).removeprefix("mdi:") for k, v in (d.get("icons") or {}).items()
                    if isinstance(k, str) and (ENTITY_RE.match(k) or (k.startswith("area:") and AREA_RE.match(k[5:])))
                    and ICON_RE.match(_str(v, 64).removeprefix("mdi:"))}
    out["kinds"] = {k: v for k, v in (d.get("kinds") or {}).items()
                    if isinstance(k, str) and ENTITY_RE.match(k) and v in KINDS}
    out["buttons"] = {k: [b for b in v if isinstance(b, str) and ENTITY_RE.match(b)][:8]
                      for k, v in (d.get("buttons") or {}).items()
                      if isinstance(k, str) and ENTITY_RE.match(k) and isinstance(v, list) and v}
    for key, dc in (("indoor_temp", "sensor."), ("indoor_humidity", "sensor.")):
        v = _str(d.get(key), 80)
        out[key] = v if v.startswith(dc) and ENTITY_RE.match(v) else ""
    out["approve_new"] = bool(d.get("approve_new", True))
    known = d.get("known")
    out["known"] = sorted({e for e in known if isinstance(e, str) and ENTITY_RE.match(e)}) if isinstance(known, list) else None
    out["seasonal"] = bool(d.get("seasonal", True))
    out["countdowns"] = [{"name": _str(c.get("name"), 30), "date": _str(c.get("date"), 5)}
                         for c in d.get("countdowns") or []
                         if isinstance(c, dict) and _str(c.get("name"), 30) and DATE_RE.match(_str(c.get("date"), 5))][:8]
    out["allow_risky"] = sorted({e for e in d.get("allow_risky") or [] if isinstance(e, str) and ENTITY_RE.match(e)})
    out["hidden"] = sorted({e for e in d.get("hidden") or [] if isinstance(e, str) and ENTITY_RE.match(e)})
    out["hidden_areas"] = sorted({a for a in d.get("hidden_areas") or [] if isinstance(a, str) and AREA_RE.match(a)})
    out["area_order"] = [a for a in d.get("area_order") or [] if isinstance(a, str) and AREA_RE.match(a)]
    out["mascot"] = d.get("mascot") if d.get("mascot") in MASCOTS else "cat"
    out["level_style"] = d.get("level_style") if d.get("level_style") in ("icons", "slider") else "icons"
    out["level_icon"] = d.get("level_icon") if d.get("level_icon") in LEVEL_ICONS else "heart"
    out["clock_24h"] = bool(d.get("clock_24h", True))
    parts = d.get("home_parts")
    out["home_parts"] = [p for p in HOME_PARTS if p in parts] if isinstance(parts, list) else list(HOME_PARTS)
    out["hello_size"] = d.get("hello_size") if d.get("hello_size") in HELLO_SIZES else "auto"
    tabs = d.get("tabs")
    out["tabs"] = list(dict.fromkeys(t for t in tabs if t in TAB_KEYS)) if isinstance(tabs, list) else list(TAB_KEYS)
    try:
        idle = int(d.get("idle_home", 300))
        out["idle_home"] = idle if idle in IDLE_CHOICES else 300
    except (TypeError, ValueError):
        pass
    for key in ("sleep_from", "sleep_to"):
        try:
            out[key] = int(d.get(key, DEFAULTS[key])) % 24
        except (TypeError, ValueError):
            pass
    out["sleep_state"] = {k: {"until": float(v.get("until") or 0), "awake_until": float(v.get("awake_until") or 0)}
                          for k, v in (d.get("sleep_state") or {}).items()
                          if isinstance(k, str) and (k == "" or KIOSK_ID_RE.match(k)) and isinstance(v, dict)}
    kiosks, ids = [], set()
    for k in d.get("kiosks") or []:
        if not isinstance(k, dict):
            continue
        kid, ip = _str(k.get("id"), 30), _str(k.get("ip"), 45)
        if not KIOSK_ID_RE.match(kid) or kid in ids or not IP_RE.match(ip):
            continue
        ids.add(kid)
        raw = k.get("settings") if isinstance(k.get("settings"), dict) else {}
        merged = clean({**out, **{key: v for key, v in raw.items() if key in KIOSK_KEYS}, "kiosks": []})
        kiosks.append({"id": kid, "name": _str(k.get("name"), 30) or kid, "ip": ip,
                       "settings": {key: merged[key] for key in KIOSK_KEYS if key in raw and merged[key] != out[key]}})
    out["kiosks"] = kiosks[:10]
    return out
