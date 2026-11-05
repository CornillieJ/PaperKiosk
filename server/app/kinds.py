"""Device kinds: what an entity *is* in the house, picked per entity on /config (config "kinds").

A kind sets the icon (on/off), whether it counts as a light (Lights tab, usage ranking, "lights on"),
and a few cute extras (the cat's lines, snow on Home for Christmas lights). Without a kind an entity
looks like its HA domain/device class (server.entity_icon). The kind never changes what a device can
do: controls come from what HA says the entity supports (light colours, climate modes, ...).

To add a kind: one line in KINDS (and its key in config.KINDS), mdi icon names from
https://pictogrammers.com/library/mdi/ (the icon set in the image is pinned, check /icon/<name>.svg).
"""

# key: (name on /config, icon when on, icon when off, counts as a light, festive)
KINDS = {
    "lamp": ("Lamp", "lamp", "lamp-outline", True, False),
    "floor": ("Floor lamp", "floor-lamp", "floor-lamp-outline", True, False),
    "ceiling": ("Ceiling light", "ceiling-light", "ceiling-light-outline", True, False),
    "desk": ("Desk lamp", "desk-lamp-on", "desk-lamp", True, False),
    "strip": ("LED strip", "led-strip-variant", "led-strip-variant-off", True, False),
    "xmas": ("Christmas lights", "string-lights", "string-lights-off", True, True),
    "tree": ("Christmas tree", "pine-tree", "pine-tree-variant-outline", True, True),
    "tv": ("TV", "television", "television-off", False, False),
    "ac": ("Air conditioner", "air-conditioner", "air-conditioner", False, False),
    "heater": ("Heater", "radiator", "radiator-off", False, False),
    "fan": ("Fan", "fan", "fan-off", False, False),
    "speaker": ("Speaker", "speaker", "speaker-off", False, False),
    "purifier": ("Air purifier", "air-purifier", "air-purifier-off", False, False),
    "coffee": ("Coffee machine", "coffee-maker", "coffee-maker-outline", False, False),
    "plug": ("Smart plug", "power-plug", "power-plug-off-outline", False, False),
}

# Colour presets for lights that support colour: (key, name, icon, hs). Grey e-ink: the name and a
# little icon say which colour it is.
COLORS = [("red", "Red", "heart", (0, 100)), ("orange", "Orange", "fire", (28, 100)),
          ("yellow", "Yellow", "star", (52, 100)), ("green", "Green", "leaf", (120, 90)),
          ("aqua", "Aqua", "waves", (180, 90)), ("blue", "Blue", "water", (225, 100)),
          ("purple", "Purple", "fruit-grapes", (275, 90)), ("pink", "Pink", "flower", (325, 75))]
# White presets for lights with colour temperature: (key, name, icon, kelvin)
WHITES = [("warm", "Warm", "candle", 2700), ("soft", "Soft", "lightbulb-on-outline", 3500),
          ("day", "Daylight", "white-balance-sunny", 5000)]
COLOR_MODES = {"hs", "xy", "rgb", "rgbw", "rgbww"}

# Words for HA's climate modes and fan modes (anything else: the HA word, capitalised)
HVAC_WORDS = {"off": ("Off", "power"), "cool": ("Cool", "snowflake"), "heat": ("Heat", "fire"),
              "heat_cool": ("Auto", "sun-snowflake-variant"), "auto": ("Auto", "sun-snowflake-variant"),
              "dry": ("Dry", "water-percent"), "fan_only": ("Fan", "fan")}


def kind_of(eid, cfg):
    return (cfg or {}).get("kinds", {}).get(eid)


def kind_icon(kind, on):
    k = KINDS.get(kind)
    return (k[1] if on else k[2]) if k else None


def light_like(s, cfg):
    """Counts as a light: HA lights (unless given a non-light kind) and anything with a light kind."""
    k = KINDS.get(kind_of(s["entity_id"], cfg))
    if k:
        return k[3]
    return s["entity_id"].startswith("light.")


def festive(eid, cfg):
    k = KINDS.get(kind_of(eid, cfg))
    return bool(k and k[4])


def word(value, words=None):
    if words and value in words:
        return words[value][0]
    text = str(value).replace("_", " ")
    return text[:1].upper() + text[1:]   # keep "HDMI 1", "YouTube" as HA has them
