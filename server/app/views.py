"""Alternative home styles (Settings > Home style; Kawaii, the default, is in kawaii.py).

Selectable styles (/v/1 .. /v/4 preview them; "/" shows the one chosen in the config):
  1 Cozy    - greeting, weather card, two device cards with a brightness slider
  2 Bubbles - big round buttons, weather as bubbles
  3 Sky     - weather first: hero, next hours, next days; devices as compact rows
  4 Paper   - calendar page and serif type, devices as switches
Each render function gets the home data `d` (see server.home_data) and the helpers `h` from server.py;
pages use the Kawaii shell and tab bar. Layout is absolute in % of the screen so it fits the Kindle
(597x750 CSS px in the kiosk app) without scrolling. Old WebKit 534: no flexbox, no CSS vars.
"""

import kawaii

GREETINGS = [(5, "Good morning", "coffee"), (12, "Good afternoon", "white-balance-sunny"),
             (18, "Good evening", "candle"), (23, "Good night", "moon-waning-crescent")]
QUOTES = ["Home is where the sofa is", "Slow mornings, warm drinks", "A little light makes everything cosy",
          "Tea first, then everything else", "Let the evening be soft", "Small things, warm home",
          "Breathe in, slow down"]
PHRASES = {"morning": "a fresh start, have a lovely day", "afternoon": "time for a little break",
           "evening": "have a cozy evening", "night": "sleep tight, little home"}


def extras(d):
    """Greeting, phrase and quote used by these styles (the Kawaii home has its cat instead)."""
    hour = d["now"].hour
    greeting, greet_icon = "Good night", "moon-waning-crescent"
    for start, text, ic in GREETINGS:
        if hour >= start:
            greeting, greet_icon = text, ic
    part = "morning" if 5 <= hour < 12 else "afternoon" if 12 <= hour < 18 else "evening" if 18 <= hour < 23 else "night"
    d.update(greeting=greeting + (f", {d['you']}" if d["you"] else ""), greet_icon=greet_icon, phrase=PHRASES[part],
             quote=QUOTES[d["now"].timetuple().tm_yday % len(QUOTES)], is_night=d["sun"]["is_night"])
    return d


# --- shared components ------------------------------------------------------------------------

def slider(h, dev, back, kind="bar", on_color="000"):
    """Tappable brightness steps for a dimmable light. kind: bar | dots | hearts | ticks."""
    if not dev["dimmable"]:
        return ""
    pct = dev["pct"] or 0
    w = 100 / len(h.levels)
    cells = ""
    for i, lvl in enumerate(h.levels):
        full = dev["on"] and pct >= lvl - 10
        if kind == "hearts":
            inner = h.icon("heart" if full else "heart-outline", on_color, "sl-ic")
        elif kind == "dots":
            inner = f'<span class="dot{" full" if full else ""}"></span>'
        elif kind == "ticks":
            inner = f'<span class="tick{" full" if full else ""}" style="height:{30 + i * 15}%"></span>'
        else:
            inner = f'<span class="cell{" full" if full else ""}"></span>'
        cells += kawaii.form(h, "level", dev["eid"], back, inner, "seg", f' style="left:{i * w:.3f}%;width:{w:.3f}%"',
                             value=lvl)
    return f'<div class="slider {kind}">{cells}</div>'


def weather_line(d):
    w = d["weather"]
    if not w:
        return ""
    return f'{w["now_text"]} · {w["temp"]}°'


def uv_text(uv):
    if uv is None:
        return "–"
    label = "low" if uv < 3 else "moderate" if uv < 6 else "high" if uv < 8 else "very high" if uv < 11 else "extreme"
    return f"{uv:g} {label}"


# --- 1 Cozy -----------------------------------------------------------------------------------

COZY_CSS = """
.greet{left:6%;right:6%;top:2.2%;font-size:19px;font-weight:700}
.greet img{width:24px;height:24px;vertical-align:-5px;margin-right:6px}
.clock{left:6%;top:6.5%;font-size:76px;font-weight:900;line-height:1;letter-spacing:-2px}
.date{left:6.5%;top:19.5%;font-size:17px;font-weight:700;color:#444}
.wcard{left:5%;right:5%;top:25.5%;height:20%;background:#eee;border-radius:26px}
.wcard .big{position:absolute;left:5%;top:50%;margin-top:-42px;width:84px;height:84px}
.wcard .t{position:absolute;left:27%;top:10%;font-size:46px;font-weight:900;line-height:1}
.wcard .c{position:absolute;left:27.5%;width:31%;top:42%;font-size:15px;font-weight:700;line-height:1.2}
.wcard .c small{display:block;font-size:13px;color:#444}
.wcard .facts{position:absolute;right:3%;top:12%;bottom:12%;width:38%;font-size:15px;font-weight:700}
.fact{height:33.3%;white-space:nowrap}
.fact img{width:20px;height:20px;vertical-align:-4px;margin-right:6px}
.sec{left:6%;right:6%;top:48.5%;font-size:20px;font-weight:900}
.sec img{width:26px;height:26px;vertical-align:-5px;margin-right:6px}
.sec small{font-size:14px;font-weight:700;color:#555;margin-left:6px}
.dcard{top:54.5%;height:38%;width:42%;border:3px solid #000;border-radius:28px;background:#fff;overflow:hidden}
.dcard.on{background:#000;color:#fff}
.dcard .main{position:absolute;left:0;right:0;top:0;bottom:0}
.dcard.dim .main{bottom:26%}
.circle{position:absolute;left:50%;top:12%;width:86px;height:86px;margin-left:-43px;border-radius:43px;background:#eee}
.on .circle{background:#fff}
.circle img{width:56px;height:56px;margin-top:15px}
.dname{position:absolute;left:0;right:0;top:56%;font-size:22px;font-weight:900}
.dstate{position:absolute;left:0;right:0;top:72%;font-size:15px;font-weight:700}
.dim .dname{top:62%}.dim .dstate{top:82%}
.slider{position:absolute;left:8%;right:8%;bottom:8%;height:16%}
.slider.bar .cell{position:absolute;left:3px;right:3px;top:30%;bottom:30%;border:2px solid currentColor;border-radius:8px}
.slider.bar .cell.full{background:currentColor}
.on .slider.bar .cell.full{background:#fff}
.sprout{left:6%;right:6%;bottom:1.2%;font-size:13px;font-weight:700;color:#555;text-align:center}
.sprout img{width:16px;height:16px;vertical-align:-3px}
"""


def device_cards(h, d, back, cls, kind="bar", body=None):
    devs = d["devices"][:2]
    out = ""
    for i, dev in enumerate(devs):
        left = 6 + i * 46 if len(devs) > 1 else 29
        on = " on" if dev["on"] else ""
        dim = " dim" if dev["dimmable"] else ""
        inner = body(dev) if body else (
            f'<span class="circle">{h.icon(dev["icon"], "000")}</span>'
            f'<span class="dname">{h.esc(dev["name"])}</span><span class="dstate">{h.esc(dev["state"])}</span>')
        main = kawaii.form(h, "toggle", dev["eid"], back, inner, "main") if dev["main"] == "toggle" else f'<div class="main">{inner}</div>'
        out += (f'<div class="abs {cls}{on}{dim}" style="left:{left}%">{main}'
                f'{slider(h, dev, back, kind, "fff" if dev["on"] else "000")}</div>')
    return out


def v1(h, d, back):
    w = d["weather"]
    wcard = ""
    if w:
        wcard = (f'<div class="abs wcard">{h.icon(w["icon"], "000", "big")}'
                 f'<div class="t">{w["temp"]}°</div><div class="c">{h.esc(w["now_text"])}'
                 f'<small>{h.esc(w["day_label"])}</small><small>{w["hi"]}° / {w["lo"]}°</small></div>'
                 f'<div class="facts"><div class="fact">{h.icon("sun-wireless-outline")}UV {h.esc(uv_text(w["uv"]))}</div>'
                 f'<div class="fact">{h.icon("umbrella-outline")}{w["rain"]} mm rain</div>'
                 f'<div class="fact">{h.icon(d["sun"]["icon"])}{h.esc(d["sun"]["label"])} {d["sun"]["time"]}</div></div></div>')
    on = sum(1 for dev in d["devices"] if dev["on"])
    body = (f'<div class="abs greet">{h.icon(d["greet_icon"])}{h.esc(d["greeting"])}</div>'
            f'<div class="abs clock">{d["time"]}</div><div class="abs date">{h.esc(d["date"])}</div>{wcard}'
            f'<div class="abs sec">{h.icon("sofa-outline")}{h.esc(d["room"])}<small>{on} of {len(d["devices"])} on</small></div>'
            + device_cards(h, d, back, "dcard") +
            f'<div class="abs sprout">{h.icon("sprout", "555")} {h.esc(d["phrase"])} {h.icon("sprout", "555")}</div>')
    return COZY_CSS, body


# --- 2 Bubbles --------------------------------------------------------------------------------

BUBBLE_CSS = """
.top{left:0;right:0;top:3%;text-align:center}
.top .clock{font-size:64px;font-weight:900;line-height:1}
.top .date{font-size:16px;font-weight:700;color:#444;margin-top:2px}
.bubbles{left:4%;right:4%;top:20%;height:15%}
.bub{position:absolute;top:0;width:30%;height:100%;text-align:center}
.bub .ring{display:block;width:92px;height:92px;margin:0 auto;border-radius:46px;border:3px solid #000;position:relative}
.bub .ring b{position:absolute;left:0;right:0;top:50%;margin-top:-16px;font-size:26px;font-weight:900;line-height:32px}
.bub .ring img{position:absolute;left:50%;top:50%;width:46px;height:46px;margin:-23px 0 0 -23px}
.bub .lbl{display:block;font-size:13px;font-weight:800;margin-top:4px}
.big2{top:41%;height:47%;width:46%;text-align:center}
.big2 .main{position:absolute;left:0;right:0;top:0;bottom:22%}
.orb{display:block;width:170px;height:170px;margin:0 auto;border-radius:85px;border:4px solid #000;background:#fff;position:relative}
.on .orb{background:#000}
.orb img{position:absolute;left:50%;top:50%;width:84px;height:84px;margin:-50px 0 0 -42px}
.orb .st{position:absolute;left:0;right:0;bottom:22px;font-size:15px;font-weight:800}
.on .orb .st{color:#fff}
.nm{display:block;font-size:22px;font-weight:900;margin-top:8px}
.slider{position:absolute;left:6%;right:6%;bottom:0;height:16%}
.slider.dots .dot{position:absolute;left:50%;top:50%;width:26px;height:26px;margin:-13px 0 0 -13px;border-radius:13px;border:3px solid #000;box-sizing:border-box;-webkit-box-sizing:border-box}
.slider.dots .dot.full{background:#000}
"""


def v2(h, d, back):
    w = d["weather"]
    bubbles = ""
    if w:
        items = [(f"<b>{w['temp']}°</b>", w["now_text"]),
                 (f"<b>{w['uv'] if w['uv'] is not None else '–'}</b>", "UV " + uv_text(w["uv"]).split(" ", 1)[-1]),
                 (h.icon(d["sun"]["icon"]), f'{d["sun"]["label"]} {d["sun"]["time"]}')]
        bubbles = '<div class="abs bubbles">' + "".join(
            f'<div class="bub" style="left:{i * 35}%"><span class="ring">{inner}</span><span class="lbl">{h.esc(lbl)}</span></div>'
            for i, (inner, lbl) in enumerate(items)) + "</div>"
    cards = ""
    devs = d["devices"][:2]
    for i, dev in enumerate(devs):
        left = 3 + i * 48 if len(devs) > 1 else 27
        on = " on" if dev["on"] else ""
        inner = (f'<span class="orb">{h.icon(dev["icon"], "fff" if dev["on"] else "000")}'
                 f'<span class="st">{h.esc(dev["state"])}</span></span><span class="nm">{h.esc(dev["name"])}</span>')
        main = kawaii.form(h, "toggle", dev["eid"], back, inner, "main") if dev["main"] == "toggle" else f'<div class="main">{inner}</div>'
        cards += f'<div class="abs big2{on}" style="left:{left}%">{main}{slider(h, dev, back, "dots")}</div>'
    body = (f'<div class="abs top"><div class="clock">{d["time"]}</div><div class="date">{h.esc(d["date"])}</div></div>'
            f'{bubbles}{cards}')
    return BUBBLE_CSS, body


# --- 3 Sky ------------------------------------------------------------------------------------

SKY_CSS = """
.hero{left:5%;right:5%;top:2.5%;height:27%}
.hero .big{position:absolute;left:0;top:4%;width:140px;height:140px}
.hero .t{position:absolute;left:44%;top:2%;font-size:84px;font-weight:900;line-height:1;letter-spacing:-2px}
.hero .c{position:absolute;left:45%;top:52%;font-size:20px;font-weight:800}
.hero .hl{position:absolute;left:45%;top:70%;font-size:15px;font-weight:700;color:#444}
.hero .time{position:absolute;right:0;top:0;font-size:18px;font-weight:900;background:#000;color:#fff;border-radius:14px;padding:2px 10px}
.strip{left:4%;right:4%;top:31%;height:15%;background:#eee;border-radius:24px}
.hr{position:absolute;top:0;bottom:0;text-align:center}
.hr .h{display:block;font-size:13px;font-weight:800;margin-top:9px}
.hr img{width:36px;height:36px;display:block;margin:3px auto}
.hr .v{display:block;font-size:17px;font-weight:900}
.days{left:4%;right:4%;top:48%;height:14%}
.day{position:absolute;top:0;bottom:0;text-align:center;border-left:2px dashed #999}
.day.first{border-left:0}
.day .n{display:block;font-size:14px;font-weight:900;margin-top:6px}
.day img{width:34px;height:34px;display:block;margin:3px auto}
.day .v{display:block;font-size:14px;font-weight:700}
.chips{left:4%;right:4%;top:64%;height:7%;font-size:14px;font-weight:800;text-align:center}
.chip{display:inline-block;border:2px solid #000;border-radius:16px;padding:3px 10px;margin:0 3px;white-space:nowrap}
.chip img{width:18px;height:18px;vertical-align:-4px;margin-right:4px}
.row{left:4%;right:4%;height:12%;border:3px solid #000;border-radius:22px;overflow:hidden}
.row.on{background:#000;color:#fff}
.row .main{position:absolute;left:0;top:0;bottom:0;width:55%}
.row .main button{text-align:left}
.row .main img{position:absolute;left:14px;top:50%;width:40px;height:40px;margin-top:-20px}
.row .nm{position:absolute;left:66px;top:50%;margin-top:-22px;font-size:20px;font-weight:900;line-height:24px}
.row .st{position:absolute;left:66px;top:50%;margin-top:3px;font-size:14px;font-weight:700}
.row .slider{position:absolute;left:55%;right:3%;top:0;bottom:0}
.row .nosl{position:absolute;left:55%;right:5%;top:50%;margin-top:-11px;text-align:right;font-size:16px;font-weight:800}
.slider.ticks .tick{position:absolute;left:25%;right:25%;bottom:22%;border:2px solid currentColor;border-radius:5px}
.slider.ticks .tick.full{background:currentColor}
"""


def v3(h, d, back):
    w = d["weather"]
    out = ""
    if w:
        out += (f'<div class="abs hero">{h.icon(w["icon"], "000", "big")}<div class="t">{w["temp"]}°</div>'
                f'<div class="c">{h.esc(w["now_text"])}</div>'
                f'<div class="hl">{h.esc(w["day_label"])} {w["hi"]}° / {w["lo"]}° · UV {h.esc(uv_text(w["uv"]))}</div>'
                f'<div class="time">{d["time"]}</div></div>')
        hours = w["hours"][:6]
        if hours:
            cw = 100 / len(hours)
            out += '<div class="abs strip">' + "".join(
                f'<div class="hr" style="left:{i * cw:.3f}%;width:{cw:.3f}%"><span class="h">{x["t"]}</span>'
                f'{h.icon(x["icon"])}<span class="v">{x["temp"]}°</span></div>' for i, x in enumerate(hours)) + "</div>"
        days = w["days"][:4]
        if days:
            cw = 100 / len(days)
            out += '<div class="abs days">' + "".join(
                f'<div class="day{" first" if i == 0 else ""}" style="left:{i * cw:.3f}%;width:{cw:.3f}%">'
                f'<span class="n">{x["day"]}</span>{h.icon(x["icon"])}<span class="v">{x["hi"]}° / {x["lo"]}°</span></div>'
                for i, x in enumerate(days)) + "</div>"
    out += (f'<div class="abs chips"><span class="chip">{h.icon(d["sun"]["icon"])}{h.esc(d["sun"]["label"])} {d["sun"]["time"]}</span>'
            f'<span class="chip">{h.icon(d["moon"]["icon"])}{h.esc(d["moon"]["name"])}</span>'
            + (f'<span class="chip">{h.icon("weather-windy")}{w["wind"]} km/h</span>' if w else "") + "</div>")
    for i, dev in enumerate(d["devices"][:2]):
        on = " on" if dev["on"] else ""
        col = "fff" if dev["on"] else "000"
        inner = f'{h.icon(dev["icon"], col)}<span class="nm">{h.esc(dev["name"])}</span><span class="st">{h.esc(dev["state"])}</span>'
        main = kawaii.form(h, "toggle", dev["eid"], back, inner, "main") if dev["main"] == "toggle" else f'<div class="main">{inner}</div>'
        extra = slider(h, dev, back, "ticks") or f'<div class="nosl">{"On" if dev["on"] else "Off"}</div>'
        out += f'<div class="abs row{on}" style="top:{73 + i * 13.5}%">{main}{extra}</div>'
    return SKY_CSS, out


# --- 4 Paper ----------------------------------------------------------------------------------

PAPER_CSS = """
#page{font-family:Bookerly,Georgia,serif}
.cal{left:6%;top:3%;width:36%;height:30%;border:3px solid #000;border-radius:18px;overflow:hidden;text-align:center}
.cal .m{background:#000;color:#fff;font-size:17px;font-weight:bold;letter-spacing:.15em;padding:6px 0;text-transform:uppercase}
.cal .n{font-size:84px;font-weight:bold;line-height:1.05}
.cal .w{font-size:17px;font-style:italic}
.side{left:48%;right:6%;top:3%;height:30%}
.side .clock{font-size:58px;font-weight:bold;line-height:1}
.side .ln{font-size:16px;margin-top:6px;white-space:nowrap}
.side .ln img{width:20px;height:20px;vertical-align:-4px;margin-right:6px}
.rule{left:6%;right:6%;height:0;border-top:2px solid #000}
.title{left:6%;right:6%;font-size:24px;font-style:italic}
.title img{width:24px;height:24px;vertical-align:-4px;margin-right:6px}
.item{left:6%;right:6%;height:11%}
.item .main{position:absolute;left:0;right:0;top:0;bottom:0}
.item .main button{text-align:left}
.item .ic{position:absolute;left:0;top:50%;width:36px;height:36px;margin-top:-18px}
.item .nm{position:absolute;left:52px;top:50%;margin-top:-22px;font-size:23px;line-height:26px}
.item .st{position:absolute;left:52px;top:50%;margin-top:6px;font-size:14px;font-style:italic;color:#444}
.switch{position:absolute;right:0;top:50%;margin-top:-19px;width:74px;height:38px;border:3px solid #000;border-radius:19px;box-sizing:border-box;-webkit-box-sizing:border-box}
.switch .k{position:absolute;top:3px;left:3px;width:26px;height:26px;border-radius:13px;background:#000}
.switch.on{background:#000}.switch.on .k{left:39px;background:#fff}
.pslider{left:6%;right:6%;height:7%}
.pslider .lbl{position:absolute;left:0;top:50%;margin-top:-10px;font-size:14px;font-style:italic;color:#444;width:22%}
.pslider .slider{position:absolute;left:22%;right:0;top:0;bottom:0}
.slider.bar .cell{position:absolute;left:3px;right:3px;top:28%;bottom:28%;border:2px solid #000;border-radius:3px}
.slider.bar .cell.full{background:#000}
.quote{left:8%;right:8%;bottom:2%;text-align:center;font-size:16px;font-style:italic;color:#333}
"""


def v4(h, d, back):
    w = d["weather"]
    lines = ""
    if w:
        lines += f'<div class="ln">{h.icon(w["icon"])}{h.esc(w["now_text"])}, {w["temp"]}°</div>'
        lines += f'<div class="ln">{h.icon("thermometer")}{w["hi"]}° / {w["lo"]}° {h.esc(w["day_label"].lower())}</div>'
        lines += f'<div class="ln">{h.icon("sun-wireless-outline")}UV {h.esc(uv_text(w["uv"]))}</div>'
    lines += f'<div class="ln">{h.icon(d["moon"]["icon"])}{h.esc(d["moon"]["name"])}</div>'
    out = (f'<div class="abs cal"><div class="m">{h.esc(d["month"])}</div><div class="n">{d["daynum"]}</div>'
           f'<div class="w">{h.esc(d["weekday"])}</div></div>'
           f'<div class="abs side"><div class="clock">{d["time"]}</div>{lines}</div>'
           f'<div class="abs rule" style="top:36%"></div>'
           f'<div class="abs title" style="top:38%">{h.icon("sofa-outline")}{h.esc(d["room"])}</div>')
    top = 46
    for dev in d["devices"][:2]:
        inner = (f'{h.icon(dev["icon"], "000", "ic")}<span class="nm">{h.esc(dev["name"])}</span>'
                 f'<span class="st">{h.esc(dev["state"])}</span>'
                 f'<span class="switch{" on" if dev["on"] else ""}"><span class="k"></span></span>')
        main = kawaii.form(h, "toggle", dev["eid"], back, inner, "main") if dev["main"] == "toggle" else f'<div class="main">{inner}</div>'
        out += f'<div class="abs item" style="top:{top}%">{main}</div>'
        top += 11.5
        if dev["dimmable"]:
            out += (f'<div class="abs pslider" style="top:{top}%"><span class="lbl">brightness</span>'
                    f'{slider(h, dev, back, "bar")}</div>')
            top += 8.5
        out += f'<div class="abs rule" style="top:{top}%;border-top:1px dashed #000"></div>'
        top += 2
    out += f'<div class="abs quote">“{h.esc(d["quote"])}”</div>'
    return PAPER_CSS, out


VIEWS = {1: ("Cozy", v1), 2: ("Bubbles", v2), 3: ("Sky", v3), 4: ("Paper", v4)}


def render(n, h, d):
    title, fn = VIEWS.get(n, VIEWS[1])
    css, body = fn(h, extras(d), "/")
    return kawaii.shell(h, title, css, body, "home", d["refresh"], d["live"])
