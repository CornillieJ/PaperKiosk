"""PaperKiosk: a Home Assistant control panel for e-ink screens (made for KUAL devices with WebKit 534, any browser).

Everything is read from Home Assistant on every page load: areas, devices and entities come from the
registries over the websocket API, so a room or device added in HA shows up here on the next refresh.
Entities with an entity category (config/diagnostic), hidden or disabled ones are left out, like HA's own
area dashboard does. Settings (home room and devices, nicknames, icons, hidden things, ...) live in
config.json, edited at /config from a PC browser (see config.py).

Modules: server.py (HA access, data, HTTP), kawaii.py (the pages; the chosen theme), views.py (the other
home styles, selectable under Settings), configpage.py (the PC config page), config.py (settings),
kinds.py (device kinds: lamp, LED strip, Christmas lights, TV, AC, ...; colour presets), fun.py (Info tab).
Pages are plain server-rendered HTML: POST forms for buttons, a meta refresh to keep states current, each
view exactly one screen (e-ink scrolls badly). Icons are Material Design Icons (same names as HA's mdi:*),
served as recoloured SVG. The HA token stays in this container. Only actions in ACTIONS on entities that
are currently shown are accepted; unlocking locks and opening garage doors/gates only for devices allowed on
/config (allow_risky). Access: see auth.py (kiosk key cookie for screens, password for /config).
"""
import base64
import hashlib
import html
import json
import math
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from websockets.sync.client import connect

import auth
import config
import configpage
import fun
import kawaii
import kinds
import pets
import views

HA_URL = os.environ.get("HA_URL", "http://host.docker.internal:8123").rstrip("/")
HA_TOKEN_FILE = os.environ.get("HA_TOKEN_FILE", "/run/secrets/ha_token")
PORT = int(os.environ.get("PORT", "8080"))
ICON_DIR = Path(os.environ.get("ICON_DIR", "/icons"))
FONT_DIR = Path(os.environ.get("FONT_DIR", "/fonts"))
KIOSK_URL = os.environ.get("PAPERKIOSK_URL", "").rstrip("/")   # shown on Settings; "" = the address the page was opened with
WS_URL = HA_URL.replace("http", "ws", 1) + "/api/websocket"
OTHER = "_other"

# Domains shown, in display order. Rooms show all of them; "Other" (no area) only controllable ones.
CONTROL_DOMAINS = ["light", "switch", "fan", "input_boolean", "cover", "lock", "climate", "humidifier",
                   "media_player", "vacuum", "select", "input_select", "scene", "script", "button", "input_button"]
INFO_DOMAINS = ["sensor", "binary_sensor"]
HOME_DOMAINS = ("light", "switch", "fan", "input_boolean", "cover", "lock", "climate", "media_player", "humidifier")
SKIP_SENSOR_CLASSES = {"timestamp", "date", "enum"}
LEVELS = (20, 40, 60, 80, 100)            # brightness as 5 icons
SLIDER_LEVELS = tuple(range(10, 101, 10))  # brightness as a slider

ONOFF_DOMAINS = ("light", "switch", "fan", "input_boolean", "media_player", "climate", "humidifier")

# action -> (domain, service, extra data); "<domain>" means the entity's own domain. A string as extra
# data means the value from the form, checked by valid_value(): "level" brightness_pct (LEVELS), "color" an
# hs preset (kinds.COLORS), "white" a colour temperature preset (kinds.WHITES), others one of the
# entity's own options (effect_list, hvac_modes, fan_modes, source_list, options).
ACTIONS = {
    "toggle": ("<domain>", "toggle", {}),
    "on": ("<domain>", "turn_on", {}),
    "off": ("<domain>", "turn_off", {}),
    "open": ("cover", "open_cover", {}),
    "close": ("cover", "close_cover", {}),
    "stop": ("cover", "stop_cover", {}),
    "lock": ("lock", "lock", {}),
    "unlock": ("lock", "unlock", {}),
    "run": ("<domain>", "turn_on", {}),
    "press": ("<domain>", "press", {}),
    "playpause": ("media_player", "media_play_pause", {}),
    "volup": ("media_player", "volume_up", {}),
    "voldown": ("media_player", "volume_down", {}),
    "warmer": ("climate", "set_temperature", None),
    "cooler": ("climate", "set_temperature", None),
    "start": ("vacuum", "start", {}),
    "dock": ("vacuum", "return_to_base", {}),
    "level": ("light", "turn_on", "level"),
    "color": ("light", "turn_on", "color"),
    "white": ("light", "turn_on", "white"),
    "effect": ("light", "turn_on", "effect"),
    "mode": ("climate", "set_hvac_mode", "hvac_mode"),
    "fanmode": ("climate", "set_fan_mode", "fan_mode"),
    "source": ("media_player", "select_source", "source"),
    "option": ("<domain>", "select_option", "option"),
}
OPTION_ATTRS = {"effect": "effect_list", "mode": "hvac_modes", "fanmode": "fan_modes", "source": "source_list",
                "option": "options"}
MAX_OPTIONS = 8   # chips per option row on a detail page


# --- Home Assistant -------------------------------------------------------------------------

def ha_token():
    try:
        token = open(HA_TOKEN_FILE).read().strip()
    except OSError:
        token = ""
    if not token:
        raise RuntimeError("No Home Assistant token yet: run ./install.sh (step: Home Assistant)")
    return token


def ha(*commands):
    """Run websocket commands (dicts without id) on one connection; returns their results."""
    with connect(WS_URL, open_timeout=5, close_timeout=2, max_size=2**24) as ws:
        ws.recv()
        ws.send(json.dumps({"type": "auth", "access_token": ha_token()}))
        if json.loads(ws.recv()).get("type") != "auth_ok":
            raise RuntimeError("Home Assistant refused the token")
        results = []
        for i, cmd in enumerate(commands, 1):
            ws.send(json.dumps({"id": i, **cmd}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == i and msg.get("type") == "result":
                    break
            if not msg.get("success"):
                raise RuntimeError(msg.get("error", {}).get("message", "command failed"))
            results.append(msg["result"])
        return results


registry_cache = {"at": 0}
registry_lock = threading.Lock()


def load(cfg, everything=False, all_states=None):
    """Rooms: [{id, name, icon, entities: [state dicts]}] in display order, plus weather and sun states.

    everything=True keeps hidden and not yet approved entities and areas (for the config page); new ones
    are marked s["new"]. all_states: a dict to fill with every state by entity id (scene buttons that are
    hidden from the rooms but used on a detail page)."""
    with registry_lock:   # registries change rarely: cache them for a minute, states are always fresh
        if time.time() - registry_cache["at"] > 60:
            areas, devices, registry, states = ha({"type": "config/area_registry/list"},
                                                  {"type": "config/device_registry/list"},
                                                  {"type": "config/entity_registry/list"},
                                                  {"type": "get_states"})
            registry_cache.update(at=time.time(), areas=areas, devices=devices, registry=registry)
        else:
            areas, devices, registry = registry_cache["areas"], registry_cache["devices"], registry_cache["registry"]
            states = ha({"type": "get_states"})[0]
    device_area = {d["id"]: d.get("area_id") for d in devices}
    reg = {e["entity_id"]: e for e in registry}
    hidden = set() if everything else set(cfg["hidden"])
    known = set(cfg["known"] or [])
    candidates = []
    rooms = {a["area_id"]: {"id": a["area_id"], "name": a["name"], "ha_icon": a.get("icon"), "entities": []}
             for a in areas}
    rooms[OTHER] = {"id": OTHER, "name": "Other", "ha_icon": "mdi:dots-grid", "entities": []}
    weathers, sun = [], None
    for s in states:
        eid, domain = s["entity_id"], s["entity_id"].split(".")[0]
        e = reg.get(eid, {})
        if e.get("entity_category") or e.get("hidden_by") or e.get("disabled_by"):
            continue
        if domain == "weather":
            weathers.append(s)
        if eid == "sun.sun":
            sun = s
        if all_states is not None:
            all_states[eid] = s
        if domain not in CONTROL_DOMAINS + INFO_DOMAINS:
            continue
        candidates.append(eid)
        if eid in hidden:
            continue
        if cfg["approve_new"] and cfg["known"] is not None and eid not in known:
            if not everything:
                continue
            s["new"] = True
        if s["state"] in ("unavailable", "unknown") and domain in INFO_DOMAINS:
            continue
        if s["state"] == "unavailable" and not cfg["show_unavailable"] and not everything:
            continue
        if domain == "sensor" and s["attributes"].get("device_class") in SKIP_SENSOR_CLASSES:
            continue
        area = e.get("area_id") or device_area.get(e.get("device_id"))
        if area not in rooms:
            if domain in INFO_DOMAINS:
                continue
            area = OTHER
        if e.get("icon") and not s["attributes"].get("icon"):
            s["attributes"]["icon"] = e["icon"]
        s["area"] = area
        rooms[area]["entities"].append(s)
    if cfg["known"] is None:   # first run: everything that exists now is known, only later additions wait
        config.update(known=candidates)
    order = CONTROL_DOMAINS + INFO_DOMAINS
    for room in rooms.values():
        room["icon"] = area_icon(room, cfg)
        room["entities"].sort(key=lambda s: (order.index(domain_of(s)), s["state"] == "unavailable",
                                             label(s, room["name"], cfg).lower()))
    out = [r for r in rooms.values() if (r["entities"] or r["id"] != OTHER)
           and (everything or r["id"] not in cfg["hidden_areas"])]
    pos = {a: i for i, a in enumerate(cfg["area_order"])}
    out.sort(key=lambda r: (r["id"] == OTHER, pos.get(r["id"], len(pos))))   # stable: HA order otherwise
    weather = next((w for w in weathers if w["entity_id"] == cfg["weather_entity"]), weathers[0] if weathers else None)
    return out, weather, sun, weathers


def call(action, entity_id, state, value=None):
    domain, service, data = ACTIONS[action]
    if domain == "<domain>":
        domain = entity_id.split(".")[0]
    if action == "run" and domain in ("button", "input_button"):
        service = "press"
    attrs = state["attributes"]
    if data == "level":
        data = {"brightness_pct": int(value)}
    elif data == "color":
        data = {"hs_color": list(next(c[3] for c in kinds.COLORS if c[0] == value))}
    elif data == "white":
        k = next(c[3] for c in kinds.WHITES if c[0] == value)
        lo, hi = attrs.get("min_color_temp_kelvin") or 2000, attrs.get("max_color_temp_kelvin") or 6500
        data = {"color_temp_kelvin": min(max(k, lo), hi)}
    elif isinstance(data, str):
        data = {data: value}
    elif data is None:  # climate: one step from the current target
        step = attrs.get("target_temp_step") or (1 if attrs.get("temperature_unit") == "°F" else 0.5)
        data = {"temperature": (attrs.get("temperature") or 20) + (step if action == "warmer" else -step)}
    ha({"type": "call_service", "domain": domain, "service": service,
        "service_data": data, "target": {"entity_id": entity_id}})


def color_modes(s):
    return set(s["attributes"].get("supported_color_modes") or []) if domain_of(s) == "light" else set()


def dimmable(s):
    return bool(color_modes(s) - {"onoff"})


def options(s, action):
    """The entity's own choices for an option action (effects, climate modes, sources, ...), max MAX_OPTIONS."""
    domain = domain_of(s)
    if action in ("mode", "fanmode") and domain != "climate" or action == "source" and domain != "media_player" \
            or action == "effect" and domain != "light" or action == "option" and domain not in ("select", "input_select"):
        return []
    vals = s["attributes"].get(OPTION_ATTRS[action]) or []
    return [str(v) for v in vals if isinstance(v, (str, int, float))][:MAX_OPTIONS]


RISKY_COVERS = ("garage", "gate", "door")


def risky(s, action):
    """Actions that let people in (unlock, open a garage door or gate): only for devices allowed on /config."""
    domain = domain_of(s)
    if domain == "lock":
        return action in ("unlock", "toggle", "open")
    if domain == "cover" and s["attributes"].get("device_class") in RISKY_COVERS:
        return action in ("open", "toggle")
    return False


def can_risky(s):
    """Is this a lock / garage door / gate (something allow_risky is about)?"""
    return domain_of(s) == "lock" or (domain_of(s) == "cover" and s["attributes"].get("device_class") in RISKY_COVERS)


def safe(acts, s, cfg):
    allowed = s["entity_id"] in (cfg or {}).get("allow_risky", [])
    return [a for a in acts if allowed or not risky(s, a)]


def main_action(s):
    """What tapping the card itself does (None: no toggle; the card opens the device page if it has one)."""
    if s["state"] == "unavailable":
        return None
    domain = domain_of(s)
    if domain in ("light", "switch", "fan", "input_boolean", "humidifier", "media_player"):
        return "toggle"
    return {"scene": "run", "script": "run", "button": "press", "input_button": "press"}.get(domain)


def control_actions(s, cfg=None):
    """Small buttons on a card (besides the brightness hearts of dimmable lights)."""
    domain, st = domain_of(s), s["state"]
    if st == "unavailable":
        return []
    if domain == "media_player":
        return ["voldown", "playpause", "volup"] if st != "off" else []
    return safe({"cover": ["open", "stop", "close"], "lock": ["lock", "unlock"], "climate": ["cooler", "warmer"],
                 "vacuum": ["start", "dock"]}.get(domain, []), s, cfg)


def detail_actions(s):
    """Everything the device page offers besides the card's controls."""
    if s["state"] == "unavailable":
        return []
    domain, modes, acts = domain_of(s), color_modes(s), []
    if domain in ONOFF_DOMAINS:
        acts += ["on", "off"]
    if dimmable(s):
        acts.append("level")
    if modes & kinds.COLOR_MODES:
        acts.append("color")
    if "color_temp" in modes:
        acts.append("white")
    acts += [a for a in OPTION_ATTRS if options(s, a)]
    return acts


def allowed_actions(s, cfg=None):
    main = main_action(s)
    acts = control_actions(s, cfg) + ([main] if main else [])
    if main and dimmable(s):
        acts.append("level")
    return safe(acts + [a for a in detail_actions(s) if a not in acts], s, cfg)


def valid_value(action, s, value):
    if action == "level":
        return value.isdigit() and int(value) in LEVELS + SLIDER_LEVELS
    if action == "color":
        return value in [c[0] for c in kinds.COLORS]
    if action == "white":
        return value in [c[0] for c in kinds.WHITES]
    if action in OPTION_ATTRS:
        return value in options(s, action)
    return True


def has_page(s, cfg):
    """Worth a device page: more than the card shows (colours, modes, sources, extra buttons, ...)."""
    if s["state"] == "unavailable":
        return False
    extra = set(detail_actions(s)) - {"on", "off", "level"}
    return bool(extra) or domain_of(s) in ("climate", "media_player") or bool(cfg.get("buttons", {}).get(s["entity_id"]))


# --- Forecast, sun, moon ----------------------------------------------------------------------

forecast_cache = {"at": 0, "entity": None, "daily": [], "hourly": []}
forecast_lock = threading.Lock()
MOON = ["New moon", "Waxing crescent", "First quarter", "Waxing gibbous", "Full moon", "Waning gibbous",
        "Last quarter", "Waning crescent"]
MOON_ICONS = ["moon-new", "moon-waxing-crescent", "moon-first-quarter", "moon-waxing-gibbous", "moon-full",
              "moon-waning-gibbous", "moon-last-quarter", "moon-waning-crescent"]
COND_TEXT = {"partlycloudy": "Partly cloudy", "clear-night": "Clear", "lightning-rainy": "Thunderstorm",
             "snowy-rainy": "Sleet", "windy-variant": "Windy", "exceptional": "Unusual weather"}


def forecasts(weather_id):
    """Daily and hourly forecasts (weather.get_forecasts), cached for 10 minutes."""
    with forecast_lock:
        if time.time() - forecast_cache["at"] > 600 or forecast_cache["entity"] != weather_id:
            out = {}
            for kind in ("daily", "hourly"):
                try:
                    r = ha({"type": "call_service", "domain": "weather", "service": "get_forecasts",
                            "service_data": {"type": kind}, "target": {"entity_id": weather_id},
                            "return_response": True})[0]
                    out[kind] = r.get("response", {}).get(weather_id, {}).get("forecast", [])
                except Exception:
                    out[kind] = forecast_cache[kind] if forecast_cache["entity"] == weather_id else []
            forecast_cache.update(at=time.time(), entity=weather_id, **out)
        return forecast_cache["daily"], forecast_cache["hourly"]


def local(iso):
    return datetime.fromisoformat(iso).astimezone()


def moon_phase(now):
    days = (now - datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)).total_seconds() / 86400
    i = int(((days % 29.530588853) / 29.530588853) * 8 + 0.5) % 8
    return {"name": MOON[i], "icon": MOON_ICONS[i]}


def cond_text(c):
    return COND_TEXT.get(c, (c or "").replace("-", " ").capitalize())


def rnd(v):
    return int(round(v)) if isinstance(v, (int, float)) else "–"


def weather_icon(cond):
    return WEATHER_ICONS.get(cond or "", "weather-partly-cloudy")


def weather_data(weather, now):
    if not weather:
        return None
    a = weather["attributes"]
    daily, hourly = forecasts(weather["entity_id"])
    evening = now.hour >= 18
    today = daily[0] if daily else {}
    day = (daily[1] if evening and len(daily) > 1 else today) if daily else {}
    hours = []
    for f in hourly:
        t = local(f["datetime"])
        if t >= now.replace(minute=0, second=0, microsecond=0) and len(hours) < 8:
            hours.append({"t": t.strftime("%H"), "icon": weather_icon(f.get("condition")),
                          "temp": rnd(f.get("temperature")), "rain": f.get("precipitation") or 0,
                          "uv": f.get("uv_index")})
    days = [{"day": local(f["datetime"]).strftime("%a"), "icon": weather_icon(f.get("condition")),
             "hi": rnd(f.get("temperature")), "lo": rnd(f.get("templow")), "rain": number(f.get("precipitation") or 0),
             "cond": cond_text(f.get("condition"))} for f in daily[1:6]]
    uv = day.get("uv_index", a.get("uv_index"))
    return {"temp": rnd(a.get("temperature")), "raw_temp": a.get("temperature"), "state": weather["state"],
            "now_text": cond_text(weather["state"]), "icon": weather_icon(weather["state"]),
            "hi": rnd(day.get("temperature")), "lo": rnd(day.get("templow")),
            "uv": round(uv, 1) if isinstance(uv, (int, float)) else None,
            "uv_now": a.get("uv_index"), "rain": number(day.get("precipitation", 0) or 0),
            "wind": rnd(a.get("wind_speed")), "humidity": rnd(a.get("humidity")),
            "day_label": "Tomorrow" if evening else "Today", "day_cond": cond_text(day.get("condition")),
            "hours": hours, "days": days}


def sun_data(sun, hour):
    out = {"label": "Sunset", "time": "–", "icon": "weather-sunset-down", "rise": "–", "set": "–",
           "is_night": hour >= 18 or hour < 7}
    if sun:
        rise, sset = sun["attributes"].get("next_rising"), sun["attributes"].get("next_setting")
        out["rise"] = local(rise).strftime("%H:%M") if rise else "–"
        out["set"] = local(sset).strftime("%H:%M") if sset else "–"
        out["is_night"] = sun["state"] == "below_horizon"
        if out["is_night"]:
            out.update(label="Sunrise", time=out["rise"], icon="weather-sunset-up")
        else:
            out.update(label="Sunset", time=out["set"], icon="weather-sunset-down")
    return out


# --- History, location ------------------------------------------------------------------------

usage_cache = {}
usage_lock = threading.Lock()
ha_config = {"at": 0, "lat": None}


def usage(ids, days):
    """Seconds each entity was on in the last `days` days (rolling: "24 h" means the same at any hour),
    from HA's history (recorder). Cached for 5 minutes. {entity_id: seconds}, plus the window length."""
    now = datetime.now().astimezone()
    start = now - timedelta(days=days)
    key = (tuple(sorted(ids)), days)
    with usage_lock:
        hit = usage_cache.get(key)
        if hit and time.time() - hit[0] < 300:
            return hit[1], hit[2]
    out = {e: 0.0 for e in ids}
    if ids:
        hist = ha({"type": "history/history_during_period", "start_time": start.isoformat(),
                   "end_time": now.isoformat(), "entity_ids": sorted(ids), "minimal_response": True,
                   "no_attributes": True, "significant_changes_only": False})[0]
        t0, t1 = start.timestamp(), now.timestamp()
        for eid, rows in hist.items():
            for i, row in enumerate(rows):
                a = max(row.get("lu", t0), t0)
                b = min(rows[i + 1].get("lu", t1), t1) if i + 1 < len(rows) else t1
                if row.get("s") == "on" and b > a and eid in out:
                    out[eid] += b - a
    span = now.timestamp() - start.timestamp()
    with usage_lock:
        if len(usage_cache) > 20:
            usage_cache.clear()
        usage_cache[key] = (time.time(), out, span)
    return out, span


def latitude():
    """Home's latitude from HA's config (for the day length on the Info tab), refreshed daily."""
    if time.time() - ha_config["at"] > 86400:
        try:
            ha_config.update(at=time.time(), lat=ha({"type": "get_config"})[0].get("latitude"))
        except Exception:
            pass
    return ha_config["lat"]


# --- Icons ----------------------------------------------------------------------------------

ICON_RE = re.compile(r"^[a-z0-9-]{1,64}$")
WEATHER_ICONS = {"clear-night": "weather-night", "cloudy": "weather-cloudy", "fog": "weather-fog",
                 "hail": "weather-hail", "lightning": "weather-lightning", "lightning-rainy": "weather-lightning-rainy",
                 "partlycloudy": "weather-partly-cloudy", "pouring": "weather-pouring", "rainy": "weather-rainy",
                 "snowy": "weather-snowy", "snowy-rainy": "weather-snowy-rainy", "sunny": "weather-sunny",
                 "windy": "weather-windy", "windy-variant": "weather-windy-variant"}
SENSOR_ICONS = {"temperature": "thermometer", "humidity": "water-percent", "illuminance": "brightness-5",
                "power": "flash", "energy": "lightning-bolt", "battery": "battery", "carbon_dioxide": "molecule-co2",
                "pressure": "gauge", "voltage": "sine-wave", "current": "current-ac", "pm25": "blur",
                "moisture": "water", "wind_speed": "weather-windy", "precipitation": "weather-rainy"}
BINARY_ICONS = {"occupancy": ("motion-sensor", "motion-sensor-off"), "motion": ("motion-sensor", "motion-sensor-off"),
                "presence": ("home-account", "home-outline"), "door": ("door-open", "door-closed"),
                "window": ("window-open", "window-closed"), "opening": ("door-open", "door-closed"),
                "moisture": ("water", "water-off"), "smoke": ("smoke-detector-alert", "smoke-detector"),
                "battery": ("battery-alert", "battery")}
COVER_ICONS = {"blind": ("blinds-open", "blinds"), "shade": ("blinds-open", "blinds"),
               "curtain": ("curtains", "curtains-closed"), "garage": ("garage-open", "garage"),
               "door": ("door-open", "door-closed"), "window": ("window-open", "window-closed")}
AREA_GUESS = [("living", "sofa"), ("lounge", "sofa"), ("kitchen", "stove"), ("bed", "bed"), ("bath", "shower"),
              ("toilet", "toilet"), ("hall", "door"), ("office", "desk"), ("study", "desk"), ("garage", "garage"),
              ("garden", "flower"), ("dining", "silverware-fork-knife"), ("laundry", "washing-machine"),
              ("kid", "teddy-bear"), ("attic", "home-roof"), ("stair", "stairs")]


def icon_exists(name):
    return bool(ICON_RE.match(name or "")) and (ICON_DIR / f"{name}.svg").is_file()


def entity_icon(s, cfg=None):
    """Icon for an entity: config override, its kind (kinds.py), HA's icon, then a cute default for its
    domain and state."""
    attrs, st, domain = s["attributes"], s["state"], domain_of(s)
    dc, on = attrs.get("device_class"), is_on(s)
    by_kind = kinds.kind_icon(kinds.kind_of(s["entity_id"], cfg), on)
    for custom in ((cfg or {}).get("icons", {}).get(s["entity_id"]), by_kind, (attrs.get("icon") or "").removeprefix("mdi:")):
        if custom and icon_exists(custom):
            return custom
    if domain == "light":
        return "lamp" if on else "lamp-outline"
    if domain == "switch":
        if dc == "outlet":
            return "power-plug" if on else "power-plug-off-outline"
        return "toggle-switch-variant" if on else "toggle-switch-variant-off"
    if domain == "input_boolean":
        return "toggle-switch" if on else "toggle-switch-off-outline"
    if domain == "fan":
        return "fan" if on else "fan-off"
    if domain == "cover":
        opened, closed = COVER_ICONS.get(dc, ("window-shutter-open", "window-shutter"))
        return opened if st in ("open", "opening") else closed
    if domain == "lock":
        return "lock-open-variant" if st == "unlocked" else "lock"
    if domain == "media_player":
        if dc == "tv":
            return "television" if st != "off" else "television-off"
        return "speaker" if st != "off" else "speaker-off"
    if domain == "sensor":
        return SENSOR_ICONS.get(dc, "eye")
    if domain == "binary_sensor":
        pair = BINARY_ICONS.get(dc, ("checkbox-marked-circle", "checkbox-blank-circle-outline"))
        return pair[0] if st == "on" else pair[1]
    if domain == "climate":
        return "air-conditioner" if st in ("cool", "dry", "fan_only") else "thermostat"
    return {"humidifier": "air-humidifier", "vacuum": "robot-vacuum", "select": "format-list-bulleted",
            "input_select": "format-list-bulleted",
            "scene": "star-four-points", "script": "script-text-play", "button": "gesture-tap-button",
            "input_button": "gesture-tap-button"}.get(domain, "help-circle-outline")


def area_icon(room, cfg):
    for custom in (cfg["icons"].get("area:" + room["id"]), (room.get("ha_icon") or "").removeprefix("mdi:")):
        if custom and icon_exists(custom):
            return custom
    name = room["name"].lower()
    return next((icon for word, icon in AREA_GUESS if word in name), "home-outline")


icon_uris = {}


ICON_PX = (72, 160)   # PNG sizes: icons up to 40 CSS px (72 Kindle px), and the big ones (up to 84 CSS px)


def icon(name, color="000", cls="ic", big=None):
    """<img> with the icon inlined as a data URI: the page arrives complete in one request (no icons popping
    in later, nothing half-loaded on the e-ink screen). As PNG near the size it is shown at, rendered here
    once: the Kindle's WebKit is slow to rasterize SVG and to scale big images down on every repaint.
    big: the large size (default for the classes "big" and "cat")."""
    if not icon_exists(name):
        name = "help-circle-outline"
    px = ICON_PX[1] if (cls in ("big", "cat") if big is None else big) else ICON_PX[0]
    key = (name, color, px)
    if key not in icon_uris:
        icon_uris[key] = icon_png_uri(name, color, px)
    return f'<img class="{cls}" src="{icon_uris[key]}" alt="">'


def icon_png_uri(name, color, px):
    svg = icon_svg(name, color).encode()
    try:
        png = subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px)], input=svg,
                             capture_output=True, timeout=5, check=True).stdout
        return "data:image/png;base64," + base64.b64encode(png).decode()
    except (OSError, subprocess.SubprocessError):   # no rsvg-convert (tests outside the image): SVG
        return "data:image/svg+xml;base64," + base64.b64encode(svg).decode()


def icon_svg(name, color):
    svg = (ICON_DIR / f"{name}.svg").read_text()
    # Explicit size: the Kindle's WebKit 534 squashes SVGs that only have a viewBox.
    return svg.replace("<svg ", f'<svg width="24" height="24" fill="#{color}" ', 1)


# --- Text -----------------------------------------------------------------------------------

def esc(v):
    return html.escape(str(v), quote=True)


def domain_of(s):
    return s["entity_id"].split(".")[0]


def label(s, room_name="", cfg=None):
    """Nickname from the config, else the friendly name without a leading room name."""
    nick = (cfg or {}).get("nicknames", {}).get(s["entity_id"])
    if nick:
        return nick
    name = s["attributes"].get("friendly_name") or s["entity_id"]
    if room_name and name.lower().startswith(room_name.lower() + " "):
        rest = name[len(room_name) + 1:].strip()
        if rest:
            name = rest
    return name[:1].upper() + name[1:]


def is_on(s):
    return s["state"] in ("on", "open", "opening", "playing", "paused", "unlocked", "heat", "cool", "heat_cool",
                          "auto", "dry", "fan_only", "cleaning")


def brightness_pct(s):
    b = s["attributes"].get("brightness")
    return round(b / 2.55) if s["state"] == "on" and b is not None else None


def number(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(f)) if f == int(f) else f"{f:.1f}"


def state_text(s):
    domain, st, a = domain_of(s), s["state"], s["attributes"]
    if st == "unavailable":
        return "Napping (unavailable)"
    if domain == "light" and st == "on":
        pct = brightness_pct(s)
        return f"On · {pct}%" if pct is not None else "On"
    if domain == "sensor":
        return f"{number(st)} {a.get('unit_of_measurement', '')}".strip()
    if domain == "binary_sensor":
        names = {"occupancy": ("Someone's here", "Empty"), "motion": ("Motion", "Still"),
                 "presence": ("Home", "Away"), "door": ("Open", "Closed"), "window": ("Open", "Closed"),
                 "opening": ("Open", "Closed"), "moisture": ("Wet!", "Dry"), "smoke": ("Smoke!", "OK"),
                 "battery": ("Low", "OK")}
        on, off = names.get(a.get("device_class"), ("On", "Off"))
        return on if st == "on" else off
    if domain == "climate":
        mode = kinds.word(st, kinds.HVAC_WORDS)
        if st == "off":
            return f"Off · {number(a.get('current_temperature', '?'))}° inside"
        return f"{mode} · {number(a.get('current_temperature', '?'))}° → {number(a.get('temperature', '?'))}°"
    if domain in ("select", "input_select"):
        return kinds.word(st)
    if domain == "media_player" and st == "playing" and a.get("media_title"):
        return f"♪ {a['media_title']}"
    if domain == "media_player" and st not in ("off", "standby") and a.get("source"):
        return f"{st.replace('_', ' ').capitalize()} · {a['source']}"
    if domain in ("scene", "script"):
        return "Tap to start"
    if domain in ("button", "input_button"):
        return "Tap to press"
    return st.replace("_", " ").capitalize()


def entity_view(s, room_name, cfg):
    """Everything a page needs to draw one entity."""
    pct = brightness_pct(s)
    return {"eid": s["entity_id"], "domain": domain_of(s), "name": label(s, room_name, cfg),
            "state": state_text(s), "raw": s["state"], "icon": entity_icon(s, cfg),
            "on": is_on(s) and domain_of(s) not in INFO_DOMAINS, "na": s["state"] == "unavailable",
            "main": main_action(s), "controls": control_actions(s, cfg), "dimmable": dimmable(s) and s["state"] != "unavailable",
            "pct": pct, "info": domain_of(s) in INFO_DOMAINS, "area": s.get("area"),
            "page": has_page(s, cfg or {}), "kind": kinds.kind_of(s["entity_id"], cfg),
            "light": kinds.light_like(s, cfg), "festive": kinds.festive(s["entity_id"], cfg),
            "mode_icon": mode_icon(s)}


def mode_icon(s):
    """Climate that is running: the icon of its mode (flame, snowflake, ...), else None."""
    if domain_of(s) != "climate" or s["state"] in ("off", "unavailable", "unknown"):
        return None
    return kinds.HVAC_WORDS.get(s["state"], ("", "thermostat"))[1]


# --- Page data --------------------------------------------------------------------------------

def common(cfg, weather, sun):
    now = datetime.now().astimezone()
    md = now.strftime("%m-%d")
    deco = None
    if cfg["seasonal"]:
        deco = "snow" if now.month == 12 or md <= "01-06" else "pumpkin" if "10-24" <= md <= "10-31" else None
    clock = now.strftime("%H:%M") if cfg["clock_24h"] else now.strftime("%-I:%M")
    return {"now": now, "time": f'<span class="clk">{clock}</span>', "date": now.strftime("%A %-d %B"),
            "weekday": now.strftime("%A"), "month": now.strftime("%B"), "daynum": now.day,
            "weather": weather_data(weather, now), "sun": sun_data(sun, now.hour), "moon": moon_phase(now),
            "cat": cfg["cat_name"], "you": cfg["your_name"], "refresh": cfg["refresh_seconds"],
            "live": cfg["live_seconds"], "deco": deco}


AUTO_HOME = ("light", "switch", "fan", "input_boolean", "climate", "cover")   # Home without picked devices


def first_sensor(rooms, area_id, device_class, chosen):
    """The chosen sensor, else the first sensor of this class in the room: its value as text, or None."""
    for r in rooms:
        for s in r["entities"]:
            if (s["entity_id"] == chosen if chosen else
                    r["id"] == area_id and s["attributes"].get("device_class") == device_class and domain_of(s) == "sensor"):
                try:
                    return number(round(float(s["state"]), 1))
                except ValueError:
                    return None
    if device_class == "temperature" and not chosen:   # no thermometer: what the room's airco measures
        for r in rooms:
            for s in r["entities"]:
                t = s["attributes"].get("current_temperature")
                if r["id"] == area_id and domain_of(s) == "climate" and isinstance(t, (int, float)):
                    return number(round(t, 1))
    return None


def indoor(rooms, area_id, cfg):
    t = first_sensor(rooms, area_id, "temperature", cfg["indoor_temp"])
    if t is None:
        return None
    return {"temp": t, "raw": float(t), "hum": first_sensor(rooms, area_id, "humidity", cfg["indoor_humidity"])}


# Bin days: the Afvalbeheer integration (RecycleApp and other collectors in the Netherlands and Belgium) makes one
# sensor per bin type with its next date in "Sort_date" (YYYYMMDD). The bin type is the last word of the sensor id.
BIN_NAMES = {"pmd": "PMD", "restafval": "Restafval", "rest": "Restafval", "gft": "GFT", "papier": "Karton",
             "glas": "Glas", "textiel": "Textiel", "grofvuil": "Grofvuil", "snoeiafval": "Snoeiafval",
             "kerstbomen": "Kerstbomen",
             # English names (sensor ids ending in these words)
             "paper": "Paper", "cardboard": "Paper", "glass": "Glass", "plastic": "Plastic", "plastics": "Plastic",
             "recycling": "Recycling", "garden": "Garden waste", "organic": "Organic", "food": "Organic",
             "general": "General waste", "residual": "General waste", "landfill": "General waste", "textile": "Textiles"}
BIN_ICONS = {"PMD": "bottle-soda-classic-outline", "Restafval": "trash-can-outline", "GFT": "leaf",
             "Karton": "package-variant-closed", "Glas": "bottle-wine-outline", "Textiel": "tshirt-crew-outline",
             "Snoeiafval": "sprout", "Kerstbomen": "pine-tree", "Paper": "package-variant-closed",
             "Glass": "bottle-wine-outline", "Plastic": "bottle-soda-classic-outline", "Recycling": "recycle",
             "Garden waste": "leaf", "Organic": "food-apple-outline", "General waste": "trash-can-outline",
             "Textiles": "tshirt-crew-outline"}


def bins_data(states, today):
    """Bins collected tomorrow: {"tomorrow": [{name, icon}]}, or None without a bin calendar in HA."""
    found, tomorrow = False, []
    for s in states.values():
        a = s["attributes"]
        if not s["entity_id"].startswith("sensor.") or "Wastecollector" not in a or "Sort_date" not in a:
            continue
        found = True
        try:
            day = datetime.strptime(str(a["Sort_date"]), "%Y%m%d").date()
        except ValueError:
            continue
        if (day - today).days != 1:
            continue
        key = s["entity_id"].rsplit("_", 1)[-1]
        name = BIN_NAMES.get(key, key.capitalize())
        if name not in [b["name"] for b in tomorrow]:
            tomorrow.append({"name": name, "icon": BIN_ICONS.get(name, "delete-outline")})
    return {"tomorrow": sorted(tomorrow, key=lambda b: b["name"])} if found else None


def home_data(cfg):
    every = {}
    rooms, weather, sun, _ = load(cfg, all_states=every)
    by_id = {s["entity_id"]: s for r in rooms for s in r["entities"]}
    main = next((r for r in rooms if r["id"] == cfg["home_area"]), None)
    room = next((r for r in rooms if r["id"] == cfg["kiosk_area"]), None) or main or (
        rooms[0] if rooms else {"id": "", "name": "Home", "entities": []})
    moved = main is not None and room["id"] != main["id"]
    if cfg["home_devices"] and not moved:
        picked = [by_id[e] for e in cfg["home_devices"] if e in by_id]
    else:
        picked = [s for s in room["entities"] if domain_of(s) in AUTO_HOME][:6 if moved else 4]
    if moved and not picked:   # a visit to a room without lights: whatever it has to control
        picked = [s for s in room["entities"] if domain_of(s) in CONTROL_DOMAINS
                  and domain_of(s) not in ("scene", "script", "button", "input_button")][:6]
    devices = [entity_view(s, room["name"], cfg) for s in picked]
    scenes = [entity_view(by_id[e], "", cfg) for e in cfg["home_scenes"] if e in by_id]
    everything = [s for r in rooms for s in r["entities"]]
    d = common(cfg, weather, sun)
    d.update(room=room["name"], room_id=room["id"], room_icon=room.get("icon", "sofa"), devices=devices,
             scenes=scenes, moved=moved, main_room=main["name"] if main else "",
             lights_on=sum(1 for s in everything if kinds.light_like(s, cfg) and is_on(s)),
             festive=any(kinds.festive(s["entity_id"], cfg) and is_on(s) for s in everything),
             indoor=indoor(rooms, room["id"], cfg), bins=bins_data(every, d["now"].date()))
    return d


def lit_count(entities, cfg):
    lights = [s for s in entities if kinds.light_like(s, cfg) and s["state"] != "unavailable"]
    return len(lights), sum(1 for s in lights if is_on(s))


def rooms_data(cfg):
    rooms, weather, sun, _ = load(cfg)
    out = []
    for r in rooms:
        lights, lit = lit_count(r["entities"], cfg)
        out.append({"id": r["id"], "name": r["name"], "icon": r["icon"], "lights": lights, "lit": lit,
                    "devices": sum(1 for s in r["entities"] if domain_of(s) not in INFO_DOMAINS),
                    "sensors": sum(1 for s in r["entities"] if domain_of(s) in INFO_DOMAINS),
                    "temp": first_sensor(rooms, r["id"], "temperature", ""),
                    "climate": next((mode_icon(s) for s in r["entities"] if mode_icon(s)), None),
                    "here": r["id"] == (cfg["kiosk_area"] or cfg["home_area"])})
    d = common(cfg, weather, sun)
    d["rooms"] = out
    d["lights_on"] = sum(r["lit"] for r in out)
    return d


def room_data(cfg, area_id):
    rooms, weather, sun, _ = load(cfg)
    room = next((r for r in rooms if r["id"] == area_id), None)
    if room is None:
        return None
    d = common(cfg, weather, sun)
    d.update(id=room["id"], name=room["name"], icon=room["icon"], other=room["id"] == OTHER,
             entities=[entity_view(s, room["name"], cfg) for s in room["entities"]])
    d["lit"] = lit_count(room["entities"], cfg)[1]
    return d


def weather_page_data(cfg):
    rooms, weather, sun, _ = load(cfg)
    d = common(cfg, weather, sun)
    d["indoor"] = indoor(rooms, cfg["kiosk_area"] or cfg["home_area"], cfg)
    return d


def duration(sec):
    m = int(sec // 60)
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m} min"


def lights_data(cfg, days):
    """Lights on now, and which lights were on longest today / this week (HA history)."""
    rooms, weather, sun, _ = load(cfg)
    lights = [(r, s) for r in rooms for s in r["entities"] if kinds.light_like(s, cfg) and domain_of(s) not in INFO_DOMAINS]
    d = common(cfg, weather, sun)
    d["on"] = [entity_view(s, r["name"], cfg) for r, s in lights if is_on(s)]
    d["days"] = days
    try:
        secs, span = usage([s["entity_id"] for _, s in lights], days)
        rank = sorted(((secs.get(s["entity_id"], 0), r, s) for r, s in lights), key=lambda x: -x[0])
        d["usage"] = {"rank": [{"name": label(s, r["name"], cfg), "room": r["name"] if r["id"] != OTHER else "",
                                "icon": entity_icon(s, cfg), "time": duration(sec), "pct": round(100 * sec / span),
                                "on": is_on(s)} for sec, r, s in rank if sec >= 60][:5],
                      "total": duration(sum(secs.values())), "ok": True}
    except Exception as exc:   # no recorder / history: the page still shows the lights that are on
        print(f"usage: {exc}", flush=True)
        d["usage"] = {"rank": [], "total": "", "ok": False}
    return d


def info_data(cfg):
    rooms, weather, sun, _ = load(cfg)
    d = common(cfg, weather, sun)
    today = d["now"].date()
    q, who = fun.quote_of(today)
    d.update(quote=q, quote_by=who, fact=fun.fact_of(d["now"]), countdowns=fun.countdowns(today, cfg["countdowns"]),
             daylight=fun.daylight(today, latitude()), year=fun.year_progress(today), season=fun.season(today))
    return d


def device_data(cfg, eid):
    """One device's page: all it can do (from HA's attributes) plus its extra buttons from the config."""
    all_states = {}
    rooms, weather, sun, _ = load(cfg, all_states=all_states)
    found = next(((r, s) for r in rooms for s in r["entities"] if s["entity_id"] == eid), None)
    if found is None:
        return None
    r, s = found
    a, acts = s["attributes"], detail_actions(s)
    d = common(cfg, weather, sun)
    current = {"effect": a.get("effect"), "mode": s["state"], "fanmode": a.get("fan_mode"),
               "source": a.get("source"), "option": s["state"]}
    if a.get("color_mode") in kinds.COLOR_MODES and a.get("hs_color"):
        hue = a["hs_color"][0]
        current["color"] = min(kinds.COLORS, key=lambda c: min(abs(c[3][0] - hue), 360 - abs(c[3][0] - hue)))[0]
    if a.get("color_mode") == "color_temp" and a.get("color_temp_kelvin"):
        current["white"] = min(kinds.WHITES, key=lambda c: abs(c[3] - a["color_temp_kelvin"]))[0]
    vol = a.get("volume_level")
    d.update(dev=entity_view(s, r["name"], cfg), room=r["name"], room_id=r["id"], acts=acts,
             opts={k: options(s, k) for k in OPTION_ATTRS if k in acts}, current=current,
             climate={"now": number(a.get("current_temperature", "–")), "target": number(a.get("temperature", "–")),
                      "unit": "°"} if domain_of(s) == "climate" else None,
             volume=round(vol * 100) if isinstance(vol, (int, float)) else None,
             buttons=[entity_view(all_states[b], "", cfg) for b in cfg["buttons"].get(eid, []) if b in all_states])
    return d


def settings_data(cfg):
    rooms, weather, sun, _ = load(cfg)
    d = {k: cfg[k] for k in ("home_style", "refresh_seconds", "live_seconds", "cat_name", "home_area", "kiosk_area")}
    d["rooms"] = [{"id": r["id"], "name": r["name"], "icon": r["icon"]} for r in rooms if r["id"] != OTHER]
    return d


def config_data(cfg):
    rooms, weather, sun, weathers = load(cfg, everything=True)
    return {"rooms": [{"id": r["id"], "name": r["name"], "icon": r["icon"],
                       "entities": [entity_view(s, r["name"], {}) | {
                           "nick": cfg["nicknames"].get(s["entity_id"], ""), "icon_cfg": cfg["icons"].get(s["entity_id"], ""),
                           "friendly": s["attributes"].get("friendly_name", ""), "new": bool(s.get("new")),
                           "kind_cfg": cfg["kinds"].get(s["entity_id"], ""), "buttons": cfg["buttons"].get(s["entity_id"], []),
                           "dc": s["attributes"].get("device_class"), "kind_icon": entity_icon(s, cfg),
                           "risky": can_risky(s), "allow_risky": s["entity_id"] in cfg["allow_risky"]}
                           for s in r["entities"]]} for r in rooms],
            "weathers": [w["entity_id"] for w in weathers], "url": KIOSK_URL}


# --- Downtime ---------------------------------------------------------------------------------

def downtime_window(cfg, now):
    """(start, end) of the downtime hours now is in, else None."""
    f, t = cfg["sleep_from"], cfg["sleep_to"]
    if f == t:
        return None
    start = now.replace(hour=f, minute=0, second=0, microsecond=0)
    if now < start:
        start -= timedelta(days=1)
    end = start + timedelta(hours=(t - f) % 24)
    return (start, end) if now < end else None


def next_wake(cfg, now):
    wake = now.replace(hour=cfg["sleep_to"], minute=0, second=0, microsecond=0)
    return wake if wake > now else wake + timedelta(days=1)


def asleep(cfg, now=None):
    """When this kiosk sleeps (downtime hours or "Going to bed"): the time it wakes up, else None."""
    now = now or datetime.now().astimezone()
    st = cfg["sleep_state"].get(cfg.get("kiosk", ""), {})
    if st.get("until", 0) > now.timestamp():
        return datetime.fromtimestamp(st["until"]).astimezone()
    win = downtime_window(cfg, now)
    if win and st.get("awake_until", 0) <= now.timestamp():
        return win[1]
    return None


def set_sleep(cfg, bed):
    """Going to bed (until the end of the next downtime) or Wake up (and stay awake for the rest of it)."""
    now = datetime.now().astimezone()
    win = downtime_window(cfg, now)
    state = dict(config.get()["sleep_state"])
    if bed:
        state[cfg.get("kiosk", "")] = {"until": next_wake(cfg, now).timestamp(), "awake_until": 0}
    else:
        state[cfg.get("kiosk", "")] = {"until": 0, "awake_until": win[1].timestamp() if win else 0}
    config.update(sleep_state=state)


def page_data(path, cfg):
    kiosk_page = path in ("/", "/rooms", "/lights", "/lights/week", "/weather", "/info", "/settings") or \
        path.startswith(("/room/", "/device/", "/v/"))
    wake = asleep(cfg) if kiosk_page else None
    if wake:
        return "sleep", {"asleep": True, "wake": wake.strftime("%H:%M" if cfg["clock_24h"] else "%-I:%M %p"),
                         "cat": cfg["cat_name"], "you": cfg["your_name"]}
    return _page_data(path, cfg)


def _page_data(path, cfg):
    """(kind, data) for a Kindle page path; None if unknown. Used to render and for /stamp."""
    if path == "/":
        return "home", home_data(cfg)
    if re.fullmatch(r"/v/[1-5]", path):
        return "home", home_data(cfg)
    if path == "/rooms":
        return "rooms", rooms_data(cfg)
    if path.startswith("/room/"):
        d = room_data(cfg, path[len("/room/"):])
        return ("room", d) if d else None
    if path == "/weather":
        return "weather", weather_page_data(cfg)
    if path == "/settings":
        return "settings", settings_data(cfg)
    if path in ("/lights", "/lights/week"):
        return "lights", lights_data(cfg, 7 if path.endswith("week") else 1)
    if path == "/info":
        return "info", info_data(cfg)
    if path.startswith("/device/"):
        d = device_data(cfg, path[len("/device/"):])
        return ("device", d) if d else None
    return None


# Left out of the page fingerprint: the clock, and numbers that drift all the time (sensor values,
# temperatures, light usage). They catch up on the next reload.
VOLATILE = {"now", "time", "date", "weekday", "daynum", "month", "refresh", "live", "usage", "indoor", "temp",
            "raw_temp", "hours", "wind", "humidity", "uv_now"}


def stamp_of(d):
    """Fingerprint of what a page shows, minus the clock and fast-changing sensor numbers.
    The page polls /stamp and reloads only when this changes."""
    def strip(v):
        if isinstance(v, dict):
            if v.get("domain") == "sensor":   # lux/power/... numbers would reload the page all the time
                v = {k: x for k, x in v.items() if k != "state"}
            return {k: strip(x) for k, x in v.items() if k not in VOLATILE}
        if isinstance(v, list):
            return [strip(x) for x in v]
        return v
    raw = json.dumps(strip(d), sort_keys=True, default=str)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


STARTED = str(time.time())   # a new server version: every page counts as changed


def page_stamp(d, cfg):
    """The page's fingerprint for live updates: its data, the settings and the server version."""
    look = json.dumps({k: v for k, v in cfg.items() if k != "known"}, sort_keys=True, default=str)
    return hashlib.sha1((stamp_of(d) + look + STARTED).encode()).hexdigest()[:12]


def helpers(cfg):
    """What the page modules get: drawing helpers plus this kiosk's look (pet, brightness style, tabs, ...)."""
    return SimpleNamespace(icon=icon, esc=esc, levels=SLIDER_LEVELS if cfg["level_style"] == "slider" else LEVELS,
                           icon_exists=icon_exists, quote=quote, pet=pets.get(cfg["mascot"]), cfg=cfg)


HELPERS = helpers(config.DEFAULTS)


# --- Actions ----------------------------------------------------------------------------------

def act(action, target, value=""):
    """Validate against what is shown right now, then call HA."""
    cfg = config.get()
    all_states = {}
    rooms, _, _, _ = load(cfg, all_states=all_states)
    if action == "alloff":
        if target == "all":
            entities = [s for r in rooms for s in r["entities"]]
        else:
            entities = next((r["entities"] for r in rooms if r["id"] == target and r["id"] != OTHER), [])
        ids = [s["entity_id"] for s in entities if kinds.light_like(s, cfg) and is_on(s)
               and domain_of(s) in ("light", "switch", "input_boolean")]
        for domain in sorted({e.split(".")[0] for e in ids}):
            ha({"type": "call_service", "domain": domain, "service": "turn_off",
                "target": {"entity_id": [e for e in ids if e.startswith(domain + ".")]}})
        return True
    shown = {s["entity_id"]: s for r in rooms for s in r["entities"]}
    state = shown.get(target)
    if state is None and action in ("run", "press"):   # an extra button on a shown device's page
        if any(target in btns for eid, btns in cfg["buttons"].items() if eid in shown) and target in all_states:
            state = all_states[target]
            if domain_of(state) not in ("scene", "script", "button", "input_button"):
                return False
            call("run", target, state)
            return True
    if state is None or action not in allowed_actions(state, cfg) or not valid_value(action, state, value):
        return False
    call(action, target, state, value)
    settle(target, state, 0.3 if action in NO_STATE_CHANGE else 1.0)
    return True


NO_STATE_CHANGE = {"volup", "voldown", "playpause", "press", "run", "stop", "start", "dock"}


def settle(entity_id, before, limit=1.0):
    """Wait until HA reports the entity changed (Zigbee/Matter devices answer in ~0.1-0.3 s), at most `limit`
    seconds, so the page that follows shows the new state."""
    end = time.time() + limit
    while time.time() < end:
        time.sleep(0.08)
        now = next((s for s in ha({"type": "get_states"})[0] if s["entity_id"] == entity_id), None)
        if now is None or now.get("last_updated") != before.get("last_updated"):
            return


# --- HTTP -----------------------------------------------------------------------------------

def render(path, query, cfg, url=""):
    """The HTML of a Kindle page (None if there is no such page). url: this server's address (Settings tab)."""
    pd = page_data(path, cfg)
    if not pd:
        return None
    kind, d = pd
    h = helpers(cfg)
    page_no = int(query["p"][0]) if query.get("p", [""])[0].isdigit() else 1
    if kind == "sleep":
        html_ = kawaii.sleep_page(h, d)
    elif kind == "home":
        style = int(path[3:]) if path.startswith("/v/") else cfg["home_style"]
        html_ = kawaii.home_page(h, d) if style == 5 else views.render(style, h, d)
    elif kind == "rooms":
        html_ = kawaii.rooms_page(h, d, page_no)
    elif kind == "room":
        html_ = kawaii.room_page(h, d, page_no)
    elif kind == "weather":
        html_ = kawaii.weather_page(h, d)
    elif kind == "lights":
        html_ = kawaii.lights_page(h, d)
    elif kind == "info":
        html_ = kawaii.info_page(h, d)
    elif kind == "device":
        html_ = kawaii.device_page(h, d, safe_back(query.get("b", [""])[0], f'/room/{quote(d["room_id"])}'), page_no)
    else:
        html_ = kawaii.settings_page(h, d, KIOSK_URL or url)
    return html_.replace(kawaii.STAMP_MARK, page_stamp(d, cfg), 1)


BACK_RE = re.compile(r"^/(?!/)[A-Za-z0-9_./?=&%-]{0,300}$")


def safe_back(back, default="/"):
    """A local path to go back to (no other site, no quotes or markup)."""
    return back if BACK_RE.match(back or "") else default


def post_act(one):
    if one.get("a") in ACTIONS or one.get("a") == "alloff":
        act(one["a"], one.get("e", ""), one.get("v", "")[:100])


def post_settings(one, kiosk=""):
    """The Kindle's Settings tab: changes the settings of the kiosk that asks (or the main ones)."""
    key, val = one.get("k"), one.get("v", "")
    if key == "home_style" and val.isdigit():
        config.update_kiosk(kiosk, home_style=int(val))
    elif key in ("refresh_seconds", "live_seconds") and val.isdigit():
        config.update_kiosk(kiosk, **{key: int(val)})
    elif key == "kiosk_area":
        config.update_kiosk(kiosk, kiosk_area=val)
    elif key == "sleep" and val in ("bed", "wake"):
        set_sleep(config.effective(config.get(), kiosk), val == "bed")


def jsonp(query, cfg, base_url=""):
    """/x.js?u=<page>[&do=act|settings&<form fields>]: runs the button's action, then returns the page as
    hk(html, url). The page script loads this with a <script> tag: after an XMLHttpRequest the Kindle's
    WebKit repaints the whole page (~1 s for these pages), after a script or image load it doesn't."""
    one = {k: v[0] for k, v in query.items()}
    if one.get("do") == "act":
        post_act(one)
        cfg = config.effective(config.get(), cfg["kiosk"])
    elif one.get("do") == "settings":
        post_settings(one, cfg["kiosk"])
        cfg = config.effective(config.get(), cfg["kiosk"])
    url = safe_back(one.get("u", "/"))
    target = urlsplit(url)
    html_ = render(target.path, parse_qs(target.query), cfg, base_url)
    if html_ is None:
        url, html_ = "/", render("/", {}, cfg, base_url)
    return f"hk({json.dumps(html_)},{json.dumps(url)})"


seen_viewports = set()
clients = {}   # IP -> (last seen, path): screens showing kiosk pages, offered when adding a kiosk on /config


def gif(width):
    """A blank 1-colour GIF of width x 1 pixels."""
    return (b"GIF89a" + bytes([width, 0, 1, 0, 0x80, 0, 0]) + b"\xff\xff\xff\x00\x00\x00"
            + b"\x2c\x00\x00\x00\x00" + bytes([width, 0, 1, 0, 0]) + b"\x02\x02\x44\x01\x00\x3b")


GIF_SAME, GIF_CHANGED = gif(1), gif(2)


PUBLIC = ("/health", "/login", "/logout", "/favicon.ico")
KIOSK_PAGES = ("/", "/rooms", "/lights", "/lights/week", "/weather", "/info", "/settings")


class Handler(BaseHTTPRequestHandler):
    server_version = "PaperKiosk"
    sys_version = ""

    def send(self, status, body="", headers=None, ctype="text/html; charset=utf-8", cache="no-store"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        for k, v in (headers or {}).items():
            if isinstance(v, list):
                for one in v:
                    self.send_header(k, one)
            else:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, where, headers=None):
        self.send(HTTPStatus.SEE_OTHER, headers={"Location": where, **(headers or {})})

    def error(self, exc):
        self.log_message("error: %s", exc)
        self.send(HTTPStatus.BAD_GATEWAY, kawaii.error_page(HELPERS, exc))

    def kiosk(self, base):
        """The id of the kiosk that is asking ("" = main settings): by IP, or the preview's hk_as cookie."""
        cookie = re.search(r"(?:^|;\s*)hk_as=([a-z0-9-]+)", self.headers.get("Cookie", ""))
        return config.kiosk_for(base, self.client_address[0], cookie.group(1) if cookie else "")

    def form(self):
        length = min(int(self.headers.get("Content-Length") or 0), 200_000)
        return parse_qs(self.rfile.read(length).decode(errors="replace"), keep_blank_values=True)

    def base_url(self):
        host = self.headers.get("Host", "")
        return f"http://{host}" if re.fullmatch(r"[A-Za-z0-9.:\[\]-]{1,100}", host) else ""

    # --- access ----------------------------------------------------------------------------

    def access(self):
        """(jar, is admin, may use the kiosk pages)."""
        jar = auth.cookies(self.headers.get("Cookie"))
        admin = auth.is_admin(jar)
        return jar, admin, admin or auth.is_kiosk(jar)

    def not_paired(self):
        if not auth.kiosk_key():
            return self.send(HTTPStatus.SERVICE_UNAVAILABLE, kawaii.message_page(
                HELPERS, "Not set up yet", "Run ./install.sh on the server first (it creates the keys)."))
        return self.send(HTTPStatus.UNAUTHORIZED, kawaii.message_page(
            HELPERS, "This screen isn't paired",
            "Open the kiosk link from the installer (it ends in ?key=...), or log in on the settings page.",
            ("/login", "Log in")))

    def pair(self, url, query):
        """?key=<kiosk key> on any page: remember this screen (cookie) and show the page. Kiosk pages are served
        right away (not redirected), so screens that never keep cookies (screenshot services, e-paper dashboards
        that fetch one URL) work with the link on every request; browsers that do keep it get the key taken out
        of the address bar."""
        if not auth.key_ok(query.get("key", [""])[0]):
            self.log_message("wrong kiosk key")
            return self.not_paired()
        ip, ua = self.client_address[0], self.headers.get("User-Agent", "")
        kind = "Kindle" if "Kindle" in ua or "armv7" in ua else "browser"
        print(f"paired: {ip} ({kind}) {re.sub(r'[^ -~]', '?', ua[:100])}", flush=True)   # scripts/50-kindle-setup.sh waits for it
        rest = urlencode([(k, v) for k, vals in query.items() if k != "key" for v in vals])
        clean = safe_back(url.path + ("?" + rest if rest else ""))
        cookie = {"Set-Cookie": auth.kiosk_cookie()}
        base = config.get()
        try:
            html_ = render(url.path, {k: v for k, v in query.items() if k != "key"},
                           config.effective(base, self.kiosk(base)), self.base_url())
        except Exception as exc:   # HA down: the error page, but the screen is paired all the same
            self.log_message("error: %s", exc)
            return self.send(HTTPStatus.BAD_GATEWAY, kawaii.error_page(HELPERS, exc), headers=cookie)
        if not html_:
            return self.redirect(clean, cookie)
        strip = (f'<script>if(window.history&&history.replaceState)history.replaceState(null,"",'
                 f'{json.dumps(clean)})</script>')   # clean: a local path without quotes or markup (safe_back)
        return self.send(HTTPStatus.OK, html_.replace("</body>", strip + "</body>", 1), headers=cookie)

    # --- GET -------------------------------------------------------------------------------

    def do_GET(self):
        url = urlsplit(self.path)
        path, query = url.path, parse_qs(url.query)
        if path == "/health":
            return self.send(HTTPStatus.OK, "ok", ctype="text/plain")
        if path.startswith("/icon/") and path.endswith(".svg"):
            name, color = path[6:-4], query.get("c", ["000"])[0]
            if not icon_exists(name) or not re.fullmatch(r"[0-9a-f]{3}", color):
                return self.send(HTTPStatus.NOT_FOUND)
            return self.send(HTTPStatus.OK, icon_svg(name, color), ctype="image/svg+xml", cache="max-age=604800")
        if re.fullmatch(r"/font/nunito-(400|700|800|900)\.woff", path):
            return self.send(HTTPStatus.OK, (FONT_DIR / path[6:]).read_bytes(), ctype="font/woff",
                             cache="max-age=2592000")
        if "key" in query:
            return self.pair(url, query)
        jar, admin, ok = self.access()
        if path == "/login":
            return self.send(HTTPStatus.OK, configpage.login_page(HELPERS, "", auth.admin_configured()))
        if path == "/logout":
            return self.redirect("/login", {"Set-Cookie": auth.logout_cookie()})
        if path == "/config":
            if not admin:
                return self.redirect("/login")
        elif not ok:
            if path == "/stamp.gif":
                return self.send(HTTPStatus.OK, GIF_CHANGED, ctype="image/gif")   # reloads into the "not paired" page
            if path == "/x.js":
                return self.send(HTTPStatus.OK, "location.reload()", ctype="application/javascript")
            return self.not_paired()
        if path == "/x.js" and "do" in query and not auth.same_site(self.headers):
            return self.send(HTTPStatus.FORBIDDEN, "", ctype="application/javascript")
        base = config.get()
        kiosk = self.kiosk(base)
        cfg = config.effective(base, kiosk)
        if path in ("/", "/stamp.gif") and len(clients) < 200:
            clients[self.client_address[0]] = (time.time(), self.headers.get("User-Agent", "")[:120])
        try:
            if path == "/ping":
                key = urlencode({k: v[0][:200] for k, v in query.items()})
                if key not in seen_viewports and len(seen_viewports) < 50:
                    seen_viewports.add(key)
                    self.log_message("viewport: %s", key)
                return self.send(HTTPStatus.NO_CONTENT)
            if path == "/stamp":   # live updates: fingerprint of the page the Kindle shows (see stamp_of)
                page = urlsplit(query.get("p", ["/"])[0]).path
                pd = page_data(page, cfg)
                return self.send(HTTPStatus.OK, page_stamp(pd[1], cfg) if pd else "gone", ctype="text/plain")
            if path == "/stamp.gif":   # the same as an image: 1x1 = unchanged, 2x1 = changed (or gone).
                # The Kindle's WebKit answers taps ~1 s late while a page polls with XMLHttpRequest; image
                # requests don't have that effect.
                page = urlsplit(query.get("p", ["/"])[0]).path
                pd = page_data(page, cfg)
                same = pd is not None and page_stamp(pd[1], cfg) == query.get("s", [""])[0]
                return self.send(HTTPStatus.OK, GIF_SAME if same else GIF_CHANGED, ctype="image/gif")
            if path == "/x.js":   # the page (after an action) as JSONP for the page script, see kawaii.CLIENT_JS
                return self.send(HTTPStatus.OK, jsonp(query, cfg, self.base_url()), ctype="application/javascript")
            if path == "/config":
                saved = query.get("saved", [""])[0] == "1"
                editing = query.get("kiosk", [""])[0]
                editing = editing if any(k["id"] == editing for k in base["kiosks"]) else ""
                data = config_data(base)
                data["url"] = data["url"] or self.base_url()
                data["clients"] = sorted(((ip, t, ua) for ip, (t, ua) in clients.items()), key=lambda c: -c[1])
                data["csrf"] = auth.csrf_token(jar)
                return self.send(HTTPStatus.OK, configpage.render(helpers(base), base, data, saved, editing,
                                                                  open_all=query.get("open", [""])[0] == "1"))
            html_ = render(path, query, cfg, self.base_url())
            if html_:
                return self.send(HTTPStatus.OK, html_)
            if path.startswith(("/room/", "/device/")):
                return self.redirect("/rooms")
        except Exception as exc:  # HA down, token revoked, ...
            return self.error(exc)
        self.redirect("/")

    # --- POST ------------------------------------------------------------------------------

    def do_POST(self):
        path = urlsplit(self.path).path
        fields = self.form()
        one = {k: v[0] for k, v in fields.items()}
        if not auth.same_site(self.headers):
            self.log_message("refused a %s from another site", path)
            return self.send(HTTPStatus.FORBIDDEN, "Forbidden: this request came from another website.", ctype="text/plain")
        jar, admin, ok = self.access()
        if path == "/login":
            return self.login(one.get("password", ""))
        back = safe_back(one.get("b", "/"))
        try:
            if path in ("/act", "/settings"):
                if not ok:
                    return self.not_paired()
                if path == "/act":
                    post_act(one)
                else:
                    post_settings(one, self.kiosk(config.get()))
                return self.redirect(back)
            if path == "/config":
                if not admin:
                    return self.redirect("/login")
                if not auth.csrf_ok(jar, one.get("csrf")):
                    return self.send(HTTPStatus.FORBIDDEN, "Forbidden: the form is out of date, reload the page.",
                                     ctype="text/plain")
                cfg, editing = configpage.parse(fields, config.get())
                config.save(cfg)
                if one.get("ajax") == "1":
                    return self.send(HTTPStatus.OK, "saved", ctype="text/plain")
                return self.redirect("/config?saved=1" + (f"&kiosk={quote(editing)}" if editing else ""))
        except Exception as exc:
            return self.error(exc)
        self.send(HTTPStatus.NOT_FOUND)

    def login(self, password):
        ip = self.client_address[0]
        if not auth.admin_configured() or not auth.kiosk_key():
            return self.send(HTTPStatus.SERVICE_UNAVAILABLE, configpage.login_page(HELPERS, "", False))
        if auth.login_blocked(ip):
            return self.send(HTTPStatus.TOO_MANY_REQUESTS, configpage.login_page(
                HELPERS, "Too many wrong passwords. Wait 15 minutes and try again.", True))
        if not auth.check_password(password):
            self.log_message("wrong admin password")
            auth.login_failed(ip)
            return self.send(HTTPStatus.UNAUTHORIZED, configpage.login_page(HELPERS, "Wrong password.", True))
        auth.login_ok(ip)
        return self.redirect("/config", {"Set-Cookie": auth.admin_cookie()})

    def log_request(self, code="-", size="-"):
        p = self.path.split("?", 1)[0]
        if not p.startswith(("/icon/", "/ping", "/health", "/stamp")):   # /font/: the Kindle should never ask
            self.log_message('"%s %s" %s', self.command, p, code)   # no query strings: keys stay out of the log


if __name__ == "__main__":
    print(f"PaperKiosk on :{PORT} -> {HA_URL}, config {config.PATH}", flush=True)
    if not auth.kiosk_key():
        print("No kiosk key in secrets/ yet: run ./install.sh. Until then only /health answers.", flush=True)
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
