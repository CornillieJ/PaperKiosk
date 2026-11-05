"""A pretend Home Assistant for tests and the demo server: a living room with lamps, an LED strip, Christmas
lights, an AC and TV (IR blaster), a kitchen, a bedroom and a hall with a front door lock and a garage door.
fake_ha(*commands) answers like server.ha(); service calls change the pretend states.
"""
import copy
import time

AREAS = [{"area_id": "living_room", "name": "Living Room", "icon": None},
         {"area_id": "kitchen", "name": "Kitchen", "icon": None},
         {"area_id": "bedroom", "name": "Bedroom", "icon": None},
         {"area_id": "hall", "name": "Hall", "icon": None}]


def st(eid, state, **attrs):
    return {"entity_id": eid, "state": state, "attributes": attrs}


BASE = [
    st("light.sofa", "on", friendly_name="Sofa", supported_color_modes=["brightness"], color_mode="brightness",
       brightness=153),
    st("switch.sidebar", "on", friendly_name="sidebar", device_class="outlet"),
    st("light.sidebar_leds", "on", friendly_name="Sidebar LEDs", supported_color_modes=["hs", "color_temp"],
       color_mode="hs", hs_color=[225, 100], brightness=200, effect_list=["Rainbow", "Breathe", "Candle", "Party"],
       effect=None, min_color_temp_kelvin=2200, max_color_temp_kelvin=6500),
    st("light.christmas", "on", friendly_name="Christmas lights", supported_color_modes=["onoff"], color_mode="onoff"),
    st("climate.living_room_ac", "cool", friendly_name="Living Room AC", hvac_modes=["off", "cool", "heat", "dry", "fan_only", "auto"],
       fan_modes=["auto", "low", "medium", "high"], fan_mode="auto", current_temperature=24.5, temperature=22,
       target_temp_step=1),
    st("media_player.tv", "on", friendly_name="TV", device_class="tv", source_list=["HDMI 1", "HDMI 2", "Netflix", "YouTube"],
       source="Netflix", volume_level=0.3),
    st("media_player.living_room_speaker", "off", friendly_name="Living room speaker", device_class="speaker"),
    st("sensor.living_room_temperature", "21.4", friendly_name="Living room temperature", device_class="temperature",
       unit_of_measurement="°C"),
    st("sensor.living_room_humidity", "48", friendly_name="Living room humidity", device_class="humidity",
       unit_of_measurement="%"),
    st("script.sidebar_red", "off", friendly_name="Sidebar red"),
    st("script.sidebar_rainbow", "off", friendly_name="Sidebar rainbow"),
    st("scene.movie_night", "2026-11-01T20:00:00", friendly_name="Movie night"),
    st("remote.ir_blaster", "on", friendly_name="IR blaster"),
    st("media_player.kitchen_display", "off", friendly_name="Kitchen display"),
    st("light.kitchen", "off", friendly_name="Kitchen", supported_color_modes=["color_temp"], color_mode="color_temp",
       color_temp_kelvin=3000, min_color_temp_kelvin=2200, max_color_temp_kelvin=6500),
    st("light.ball", "unavailable", friendly_name="Ball", supported_color_modes=["color_temp", "hs", "xy"]),
    st("light.hall", "off", friendly_name="Hall", supported_color_modes=["color_temp", "hs", "xy"]),
    st("light.stairs", "on", friendly_name="Stairs", supported_color_modes=["color_temp", "hs", "xy"], color_mode="color_temp",
       color_temp_kelvin=2700, brightness=255),
    st("sensor.hall_sensor_illuminance", "3", friendly_name="Hall sensor Illuminance", device_class="illuminance",
       unit_of_measurement="lx"),
    st("binary_sensor.hall_sensor_occupancy", "off", friendly_name="Hall sensor Occupancy", device_class="occupancy"),
    st("lock.front_door", "locked", friendly_name="Front door"),
    st("cover.garage_door", "closed", friendly_name="Garage door", device_class="garage"),
    st("weather.forecast_home", "cloudy", friendly_name="Forecast Home", temperature=9.2, humidity=81, wind_speed=14,
       uv_index=1.2),
    st("sun.sun", "above_horizon", next_rising="2026-11-05T06:55:00+00:00", next_setting="2026-11-04T16:20:00+00:00"),
]
AREA_OF = {"light.sofa": "living_room", "switch.sidebar": "living_room", "light.sidebar_leds": "living_room",
           "light.christmas": "living_room", "climate.living_room_ac": "living_room", "media_player.tv": "living_room",
           "media_player.living_room_speaker": "living_room", "sensor.living_room_temperature": "living_room",
           "sensor.living_room_humidity": "living_room", "remote.ir_blaster": "living_room",
           "media_player.kitchen_display": "kitchen", "light.kitchen": "kitchen", "light.ball": "bedroom",
           "light.hall": "hall", "light.stairs": "hall", "sensor.hall_sensor_illuminance": "hall",
           "binary_sensor.hall_sensor_occupancy": "hall", "lock.front_door": "hall", "cover.garage_door": "hall"}

STATES = {}
CALLS = []
FORECAST = {"daily": [{"datetime": f"2026-11-0{4 + i}T11:00:00+00:00", "condition": c, "temperature": t, "templow": t - 5,
                       "precipitation": p, "uv_index": 1} for i, (c, t, p) in
                      enumerate([("cloudy", 11, 0.2), ("rainy", 10, 4), ("partlycloudy", 12, 0), ("sunny", 13, 0),
                                 ("rainy", 9, 6), ("cloudy", 10, 1)])],
            "hourly": []}


def bins(days):
    """Afvalbeheer (RecycleApp) sensors: bin type -> days until its next pickup."""
    from datetime import date, timedelta
    for key, n in days.items():
        day = date.today() + timedelta(days=n)
        STATES[f"sensor.afvalbeheer_recycleapp_recycle_{key}"] = st(
            f"sensor.afvalbeheer_recycleapp_recycle_{key}", day.strftime("%d-%m-%Y"), Wastecollector="recycleapp",
            Hidden=False, Sort_date=int(day.strftime("%Y%m%d")), Days_until=n)
    STATES["sensor.afvalbeheer_recycleapp_recycle_morgen"] = st("sensor.afvalbeheer_recycleapp_recycle_morgen", "Geen",
                                                                Wastecollector="recycleapp", Hidden=True)


def reset():
    STATES.clear()
    for s in copy.deepcopy(BASE):
        STATES[s["entity_id"]] = s
    bins({"pmd": 1, "gft": 1, "restafval": 6, "papier": 13})
    CALLS.clear()


reset()


def history(ids, start, end):
    """Every light on for a different share of the window."""
    t0, t1 = start, end
    out = {}
    for n, eid in enumerate(sorted(ids)):
        share = [0.42, 0.3, 0.18, 0.08, 0.04, 0.02, 0.0][n % 7]
        rows = [{"s": "off", "lu": t0}]
        if share:
            on_at = t0 + (t1 - t0) * (1 - share)
            rows.append({"s": "on", "lu": on_at})
        out[eid] = rows
    return out


def service(cmd):
    domain, service_, data = cmd["domain"], cmd["service"], dict(cmd.get("service_data") or {})
    targets = cmd.get("target", {}).get("entity_id", [])
    targets = [targets] if isinstance(targets, str) else targets
    CALLS.append((domain, service_, tuple(targets), data))
    if domain == "weather":
        kind = data["type"]
        return {"response": {targets[0]: {"forecast": FORECAST[kind]}}}
    for eid in targets:
        s = STATES.get(eid)
        if not s:
            continue
        s["last_updated"] = str(time.time())
        a = s["attributes"]
        if service_ == "toggle":
            s["state"] = "off" if s["state"] not in ("off",) else "on"
        elif service_ == "turn_on":
            if domain in ("light", "switch", "media_player", "input_boolean", "fan"):
                s["state"] = "on"
            elif domain == "climate":
                s["state"] = "cool"
            for k in ("hs_color", "color_temp_kelvin", "effect"):
                if k in data:
                    a[k] = data[k]
                    a["color_mode"] = {"hs_color": "hs", "color_temp_kelvin": "color_temp"}.get(k, a.get("color_mode"))
            if "brightness_pct" in data:
                a["brightness"] = round(data["brightness_pct"] * 2.55)
        elif service_ == "turn_off":
            s["state"] = "off"
        elif service_ == "set_hvac_mode":
            s["state"] = data["hvac_mode"]
        elif service_ == "set_fan_mode":
            a["fan_mode"] = data["fan_mode"]
        elif service_ == "set_temperature":
            a["temperature"] = data["temperature"]
        elif service_ in ("lock", "unlock"):
            s["state"] = service_ + "ed"
        elif service_ in ("open_cover", "close_cover"):
            s["state"] = "open" if service_ == "open_cover" else "closed"
        elif service_ == "select_source":
            a["source"] = data["source"]
    return {}


def fake_ha(*commands):
    out = []
    for cmd in commands:
        t = cmd["type"]
        if t == "config/area_registry/list":
            out.append(copy.deepcopy(AREAS))
        elif t == "config/device_registry/list":
            out.append([])
        elif t == "config/entity_registry/list":
            out.append([{"entity_id": e, "area_id": AREA_OF.get(e)} for e in STATES])
        elif t == "get_states":
            out.append(copy.deepcopy(list(STATES.values())))
        elif t == "get_config":
            out.append({"latitude": 50.85})
        elif t == "history/history_during_period":
            from datetime import datetime
            start = datetime.fromisoformat(cmd["start_time"]).timestamp()
            end = datetime.fromisoformat(cmd["end_time"]).timestamp()
            out.append(history(cmd["entity_ids"], start, end))
        elif t == "call_service":
            out.append(service(cmd))
        else:
            raise RuntimeError(f"fake HA: unknown command {t}")
    return out


def now():
    return time.time()
