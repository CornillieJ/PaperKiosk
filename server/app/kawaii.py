"""Kawaii: the PaperKiosk theme. Every page except the alternative home styles (views.py) and /config.

Pages: Home (home_page), Rooms (rooms_page), a room (room_page), a device (device_page), Lights (lights_page:
on now + usage ranking), Weather, Info (info_page: quote, fun fact, countdowns; nothing about the house),
Settings (home style, move kiosk, updates), error.
Look: Nunito, black on white e-ink, rounded cards, dashed outlines, paws/hearts/sparkles, a cat
(the name is configurable) that comments on the time of day, weather and lights. Things that are
on are drawn inverted (black card, white text).

Layout rules (Kindle, WebKit 534): one screen per page, absolute positions in % of #page height and
px sizes designed for a 597 CSS px wide screen (the kiosk app zooms to it, see KINDLE_ZOOM). No flexbox,
no calc(), no CSS variables; ES5 at most. Buttons are POST forms; every tap reloads the page.
"""
import math
import time

import kinds
import pets

KINDLE_ZOOM = ("<script>(function(){var w=window.innerWidth||document.documentElement.clientWidth;"
               "if(/armv7l/.test(navigator.userAgent)&&w>800){document.documentElement.style.zoom=w/597}})()</script>")
PING = ("<script>try{var i=new Image();i.src='/ping?w='+window.innerWidth+'&h='+window.innerHeight+"
        "'&d='+(window.devicePixelRatio||1)+'&ua='+encodeURIComponent(navigator.userAgent)}catch(e){}</script>")

STAMP_MARK = "__HK_STAMP__"   # replaced by server.stamp_of(page data) after rendering


CLIENT_JS = """(function(){
var st='__HK_STAMP__',every=__LIVE__,full=__FULL__,home=__HOME__,h12=__H12__,busy=0,d=document,touched=new Date().getTime();
function p(n){return n<10?'0'+n:''+n}
function clock(){var t=new Date(),hr=t.getHours(),c=(h12?((hr+11)%12+1):p(hr))+':'+p(t.getMinutes()),e=d.getElementsByClassName('clk');
 for(var i=0;i<e.length;i++){if(e[i].innerHTML!=c)e[i].innerHTML=c}}
function here(){return location.pathname+location.search}
function hard(url){location.href=url}
function patch(o,n){var oc=o.children,nc=n.children;
 if(oc.length!=nc.length){o.innerHTML=n.innerHTML;return}
 for(var i=nc.length-1;i>=0;i--){if(oc[i].outerHTML!=nc[i].outerHTML)o.replaceChild(nc[i],oc[i])}}
function swap(html,url){
 var b=html.match(/<body[^>]*>([\\s\\S]*)<\\/body>/),c=html.match(/<style>([\\s\\S]*?)<\\/style>/),
  t=html.match(/<title>([^<]*)<\\/title>/),k=html.match(/var st='([^']*)'/);
 if(!b||!c||!history.replaceState){hard(url);return}
 var old=d.getElementsByTagName('style')[0],tmp=d.createElement('div');tmp.innerHTML=b[1];
 var np=tmp.querySelector('#page'),nt=tmp.querySelector('#tabs'),op=d.getElementById('page'),ot=d.getElementById('tabs');
 if(old.textContent==c[1]&&np&&nt&&op&&ot){patch(op,np);patch(ot,nt)}
 else{var ns=d.createElement('style');ns.appendChild(d.createTextNode(c[1]));old.parentNode.replaceChild(ns,old);
  d.body.innerHTML=b[1]}
 if(k)st=k[1];if(url!=here())history.replaceState(null,'',url);clock()}
function load(url,extra){
 if(busy)return;busy=1;var sc=d.createElement('script'),hd=d.getElementsByTagName('head')[0],
  timer=setTimeout(function(){hard(url)},15000);
 window.hk=function(html,to){clearTimeout(timer);busy=0;try{swap(html,to)}catch(e){hard(to)}
  if(sc.parentNode)sc.parentNode.removeChild(sc)};
 sc.onerror=function(){clearTimeout(timer);hard(url)};
 sc.src='/x.js?u='+encodeURIComponent(url)+(extra?'&'+extra:'')+'&t='+(new Date()).getTime();hd.appendChild(sc)}
function up(e,tag){while(e&&e.nodeName!=tag){e=e.parentNode}return e}
function pressed(e){if(e&&e.className!==undefined)e.className+=' tap'}
d.addEventListener('mousedown',function(){touched=new Date().getTime()},true);
d.addEventListener('click',function(ev){
 var a=up(ev.target,'A');if(!a)return;var h=a.getAttribute('href');
 if(!h||h.charAt(0)!='/'||a.target)return;ev.preventDefault();if(busy)return;pressed(a);load(h)},true);
d.addEventListener('submit',function(ev){
 var f=ev.target,q=[],back=here(),els=f.getElementsByTagName('input');ev.preventDefault();if(busy)return;
 for(var i=0;i<els.length;i++){q.push(encodeURIComponent(els[i].name)+'='+encodeURIComponent(els[i].value));
  if(els[i].name=='b')back=els[i].value}
 q.push('do='+(f.getAttribute('action')=='/act'?'act':'settings'));
 pressed(f.getElementsByTagName('button')[0]);load(back,q.join('&'))},true);
function check(){if(busy)return;var i=new Image();
 i.onload=function(){if(i.width>1&&!busy)load(here())};
 i.src='/stamp.gif?p='+encodeURIComponent(location.pathname)+'&s='+st+'&t='+(new Date()).getTime()}
function idle(){if(!busy&&location.pathname!='/'&&new Date().getTime()-touched>home)load('/')}
clock();setInterval(clock,5000);if(every>0)setInterval(check,every);
if(full>0)setTimeout(function(){hard(here())},full);if(home>0)setInterval(idle,15000)})()"""
HOME_AFTER = 300   # seconds without a tap on another tab, then back to Home


def live_script(live, refresh=600, idle=HOME_AFTER, h12=False):
    """The page's one script (ES5, WebKit 534). The clock (.clk) ticks locally. Taps on links and buttons don't
    reload the page: the next page (after the button's action) is fetched in the background as /x.js with a
    <script> tag (not XMLHttpRequest: after one the Kindle repaints the whole page, ~1 s) and swapped in, so only what
    changed is redrawn: on the same page (a button, a live update) only the boxes that differ are replaced.
    A small change reaches the e-ink screen in ~30 ms, a full page load took ~850 ms and flashed. The tapped
    button turns grey at once (.tap). Every `live` seconds the page asks /stamp whether what it shows changed
    in HA (an image request: /stamp.gif answers 1x1 = same, 2x1 = changed; polling with XMLHttpRequest made the
    Kindle answer every tap ~1 s late) and swaps itself in the same way. Anything unexpected falls back to a
    normal page load. Every `refresh`
    seconds a real reload clears e-ink ghosting; after HOME_AFTER seconds without a tap it goes back to Home."""
    js = (CLIENT_JS.replace("__HK_STAMP__", STAMP_MARK).replace("__LIVE__", str(int(live) * 1000))
          .replace("__FULL__", str(int(refresh) * 1000)).replace("__HOME__", str(int(idle) * 1000 if live else 0))
          .replace("__H12__", "1" if h12 else "0"))
    return "<script>" + js + "</script>"


TABS = [("home", "/", "home-heart", "Home"), ("rooms", "/rooms", "home-group", "Rooms"),
        ("lights", "/lights", "lightbulb-group", "Lights"), ("weather", "/weather", "weather-partly-cloudy", "Weather"),
        ("info", "/info", "creation", "Info"), ("settings", "/settings", "cog-outline", "Settings")]
STYLES = [(5, "Kawaii", "cat"), (1, "Cozy", "sofa-outline"), (2, "Bubbles", "circle-double"),
          (3, "Sky", "weather-partly-cloudy"), (4, "Paper", "notebook-outline")]
LIVE_LABELS = [(3, "3 s"), (5, "5 s"), (10, "10 s"), (30, "30 s"), (0, "Off")]
REFRESH_LABELS = [(300, "5 min"), (600, "10 min"), (1800, "30 min"), (0, "Off")]
PER_PAGE = 6

# Nunito. On the Kindle it is installed as a system font, "Kiosk Nunito" (kindle/extension/fonts,
# registered with fontconfig by register.sh): as a web font, reloaded with every page, the Kindle's WebKit starts
# dropping letters after some hours. Browsers without it (the PC preview) download the WOFF; local() first, so
# even a fallback to "Nunito" on the Kindle never downloads anything.
FONT_CSS = "".join(
    f'@font-face{{font-family:"Nunito";src:local("Kiosk Nunito"),url(/font/nunito-{w}.woff) format("woff");'
    f'font-weight:{w};font-style:normal}}' for w in (400, 700, 800, 900))

BASE_CSS = FONT_CSS + """
html,body{margin:0;padding:0;height:100%;overflow:hidden;background:#fff;color:#000}
body{font-family:"Kiosk Nunito","Nunito",Futura,"Amazon Ember",Helvetica,sans-serif;font-size:18px;position:relative}
a,a *{color:inherit;text-decoration:none}
form{margin:0;padding:0}
button{display:block;position:relative;width:100%;height:100%;margin:0;padding:0;border:0;background:transparent;color:inherit;
  font:inherit;-webkit-appearance:none;border-radius:0;cursor:pointer;text-align:center}
.abs{position:absolute}
.tap,a.tap,button.tap{background:#888 !important;border-radius:inherit}
.vc{position:absolute;top:50%;left:0;right:0;-webkit-transform:translateY(-50%);transform:translateY(-50%)}
.seg{position:absolute;top:0;bottom:0}
.slider .trk{position:absolute;left:0;right:0;top:50%;height:16px;margin-top:-8px;border:3px solid #000;border-radius:8px;
  box-sizing:border-box;-webkit-box-sizing:border-box;background:#fff}
.slider .fill{position:absolute;left:0;top:0;bottom:0;background:#000;border-radius:5px}
.slider .knob{position:absolute;top:50%;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:17px;background:#000;
  border:3px solid #fff;box-sizing:border-box;-webkit-box-sizing:border-box;text-align:center}
.slider .knob img{position:static;width:18px;height:18px;margin:5px 0 0 0}
.on .slider .trk{border-color:#fff;background:#000}.on .slider .fill{background:#fff}
.on .slider .knob{background:#fff;border-color:#000}
.dslider{height:7.4%}
#page{position:absolute;left:0;right:0;top:0;bottom:74px;overflow:hidden}
#tabs{position:absolute;left:0;right:0;bottom:0;height:74px;border-top:3px solid #000;background:#fff}
.tab{position:absolute;top:0;bottom:0;width:16.667%;text-align:center}
.tab a{position:absolute;left:4px;right:4px;top:7px;bottom:7px;border-radius:20px;display:block}
.tab img{width:30px;height:30px;display:block;margin:5px auto 0}
.tab span{display:block;font-size:13px;line-height:17px;font-weight:900;white-space:nowrap}
.tab.on a{background:#000;color:#fff}
.tab .paw{position:absolute;right:6px;top:5px;width:12px;height:12px;margin:0}
/* sub-page header */
.hd{left:4%;right:4%;top:1.6%;height:10%}
.hd .hl{position:absolute;left:0;right:150px;top:50%;margin-top:-25px;height:50px;white-space:nowrap;overflow:hidden}
.chip{display:inline-block;vertical-align:top;height:50px;background:#000;color:#fff;position:relative;
  padding:0 22px 0 14px;font-size:22px;font-weight:900;line-height:50px;white-space:nowrap}
.chip img{width:30px;height:30px;vertical-align:-7px;margin-right:8px}
.hd .back{position:absolute;left:0;top:50%;margin-top:-25px;width:50px;height:50px;border:3px solid #000;border-radius:25px;
  box-sizing:border-box;-webkit-box-sizing:border-box;text-align:center}
.hd .back img{width:30px;height:30px;margin-top:7px}
.hd .withback{left:62px}
.hd .sub{display:inline-block;vertical-align:top;line-height:50px;margin-left:10px;font-size:15px;font-weight:800;color:#444}
.hd .now{position:absolute;right:0;top:50%;margin-top:-17px;font-size:26px;font-weight:900;line-height:34px}
.hd .now img{width:28px;height:28px;vertical-align:-6px;margin-right:4px}
/* cards */
.card{position:absolute;border:3px solid #000;background:#fff}
.card.on{background:#000;color:#fff}
.card.na{border-style:dashed;border-color:#888;color:#888}
.card.info{border:3px dashed #000}
.card .hit{position:absolute;left:0;right:0;top:0;bottom:0;text-align:center}
.card .paw{position:absolute;right:12px;top:11px;width:20px;height:20px}
.card a.more{position:absolute;right:8px;top:8px;width:42px;height:42px;border:3px solid #000;border-radius:21px;
  background:#fff;box-sizing:border-box;-webkit-box-sizing:border-box;text-align:center}
.card a.more img{width:26px;height:26px;margin-top:5px}
.card a.hit{display:block}
.hearts{position:absolute;left:5%;right:5%;bottom:3%;height:21%}
.hearts img{position:absolute;left:50%;top:50%;width:30px;height:30px;margin:-15px 0 0 -15px}
.ctl{position:absolute;left:5%;right:5%;bottom:4%;height:22%}
.ctl .seg span{position:absolute;left:50%;top:50%;width:44px;height:44px;margin:-22px 0 0 -22px;border:3px solid currentColor;
  border-radius:22px;box-sizing:border-box;-webkit-box-sizing:border-box}
.ctl .seg img{width:26px;height:26px;margin-top:6px}
.strip{left:4%;right:4%;bottom:1.5%;height:10.5%}
.pill{position:absolute;top:50%;margin-top:-25px;height:50px;border-radius:25px;background:#000;color:#fff;
  font-size:17px;font-weight:900;line-height:50px;white-space:nowrap;padding:0 18px}
.pill img{width:24px;height:24px;vertical-align:-6px;margin-right:6px}
.pill button{padding:0;line-height:50px}
.pill.light{background:#fff;color:#000;border:3px solid #000;line-height:44px;height:44px;margin-top:-25px}
.pager{position:absolute;left:0;top:50%;margin-top:-25px;height:50px;white-space:nowrap}
.pager a,.pager span.dis{display:inline-block;width:50px;height:50px;border:3px solid #000;border-radius:25px;
  box-sizing:border-box;-webkit-box-sizing:border-box;text-align:center;vertical-align:top}
.pager span.dis{border-color:#bbb}
.pager img{width:30px;height:30px;margin-top:7px}
.pager b{display:inline-block;width:64px;text-align:center;font-size:18px;font-weight:900;line-height:50px}
.deco{position:absolute;width:18px;height:18px}
"""


# --- rounded corners ----------------------------------------------------------------------------
# The Kindle's WebKit draws a border-radius box as an anti-aliased path over its whole area: a page of big
# rounded cards took ~500 ms more to paint than the same page with square ones. So big boxes are square
# and get four small corner pieces (corners()): a page-coloured square with a quarter of a rounded box in it.
# Only those small pieces are drawn as paths. The box needs position:absolute (or relative), no overflow:hidden
# and z-index:0 (in CORNER_CSS): the pieces are at z-index -1, over the box's border, under its content.

def corners(r=28):
    return "".join(f'<b class="k k{r} k{c}"><i></i></b>' for c in ("tl", "tr", "bl", "br"))


def corner_css(r):
    return (f".k{r},.k{r} i{{width:{r}px;height:{r}px}}.k{r}.ktl i{{border-top-left-radius:{r}px}}"
            f".k{r}.ktr i{{border-top-right-radius:{r}px}}.k{r}.kbl i{{border-bottom-left-radius:{r}px}}"
            f".k{r}.kbr i{{border-bottom-right-radius:{r}px}}")


CORNER_CSS = """
.card,.hello,.bubble,.stick,.stk,.hero,.fact,.hours,.day .in,.nap,.cal,.yr,.dl,.qt,.ft,.cd,.dh,.cfg,.chip,.ch,.rf,.sty,
.scenes form,.bed,.wake{z-index:0}
.k{position:absolute;display:block;background:#fff;z-index:-1}
.k i{position:absolute;left:0;top:0;display:block;border:0 solid #000;background:#fff;
  box-sizing:border-box;-webkit-box-sizing:border-box}
.k.ktl i{border-top-width:3px;border-left-width:3px}.k.ktr i{border-top-width:3px;border-right-width:3px}
.k.kbl i{border-bottom-width:3px;border-left-width:3px}.k.kbr i{border-bottom-width:3px;border-right-width:3px}
.k.ktl{left:-3px;top:-3px}.k.ktr{right:-3px;top:-3px}.k.kbl{left:-3px;bottom:-3px}.k.kbr{right:-3px;bottom:-3px}
.nob>.k.ktl{left:0;top:0}.nob>.k.ktr{right:0;top:0}.nob>.k.kbl{left:0;bottom:0}.nob>.k.kbr{right:0;bottom:0}
.nob>.k i{border-width:0 !important}
.on>.k i,.dark>.k i{background:#000}
.dash>.k i,.info>.k i{border-style:dashed}
.na>.k i{border-style:dashed;border-color:#888}
""" + "".join(corner_css(r) for r in (20, 22, 24, 26, 28, 30))


# --- small helpers ----------------------------------------------------------------------------

def form(h, action, target, back, inner, cls="", style="", value=None, r=None):
    """A button: POST /act a=action e=target b=back [v=value]. r: rounded box with corner pieces (corners())."""
    val = f'<input type="hidden" name="v" value="{h.esc(value)}">' if value is not None else ""
    return (f'<form method="post" action="/act" class="{cls}"{style}>{corners(r) if r else ""}'
            f'<input type="hidden" name="a" value="{h.esc(action)}">'
            f'<input type="hidden" name="e" value="{h.esc(target)}"><input type="hidden" name="b" value="{h.esc(back)}">'
            f'{val}<button>{inner}</button></form>')


def setting(h, key, value, back, inner, cls="", style="", r=None):
    return (f'<form method="post" action="/settings" class="{cls}"{style}>{corners(r) if r else ""}'
            f'<input type="hidden" name="k" value="{h.esc(key)}">'
            f'<input type="hidden" name="v" value="{h.esc(value)}"><input type="hidden" name="b" value="{h.esc(back)}">'
            f'<button>{inner}</button></form>')


def tabbar(h, active):
    """Home plus the tabs this kiosk shows (config "tabs"), as wide as there is room for."""
    keys = ["home"] + h.cfg["tabs"]
    shown = sorted((t for t in TABS if t[0] in keys), key=lambda t: keys.index(t[0]))
    w = 100 / len(shown)
    out = ""
    for i, (key, href, ic, label) in enumerate(shown):
        on = key == active
        paw = h.icon("paw", "fff", "paw") if on else ""
        out += (f'<div class="tab{" on" if on else ""}" style="left:{i * w:.3f}%;width:{w:.3f}%"><a href="{href}">{paw}'
                f'{h.icon(ic, "fff" if on else "000", "")}<span>{label}</span></a></div>')
    return f'<div id="tabs">{out}</div>'


def shell(h, title, css, body, active, refresh=600, live=5, idle=None, tabs=True):
    # Without live updates (error page) a meta refresh; otherwise the script reloads (a meta refresh would go
    # back to the first page loaded, not the one swapped in).
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh and not live else ""
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8">{meta}'
            f'<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">'
            f'<title>{h.esc(title)}</title><style>{BASE_CSS}{CORNER_CSS}{css}</style>{KINDLE_ZOOM}</head>'
            f'<body><div id="page">{pets.say(h.pet, body)}</div>{tabbar(h, active) if tabs else ""}'
            f'{live_script(live, refresh, h.cfg["idle_home"] if idle is None else idle, not h.cfg["clock_24h"])}{PING}</body></html>')


def header(h, d, title, ic, sub="", back=None):
    left = ""
    if back:
        left = f'<a class="back" href="{h.esc(back)}">{h.icon("chevron-left")}</a>'
    w = d.get("weather")
    now = (f'{h.icon(w["icon"])}{w["temp"]}° · ' if w else "") + d["time"]
    subt = f'<span class="sub">{h.esc(sub)}</span>' if sub else ""
    return (f'<div class="abs hd">{left}<div class="hl{" withback" if back else ""}">'
            f'<span class="chip nob dark">{corners(24)}{h.icon(ic, "fff")}{h.esc(title)}</span>{subt}</div><div class="now">{now}</div></div>')


# Brightness icons (config "level_icon"): (full, empty)
LEVEL_ICONS = {"heart": ("heart", "heart-outline"), "star": ("star", "star-outline"), "paw": ("paw", "paw-outline"),
               "flower": ("flower", "flower-outline"),
               "circle": ("checkbox-blank-circle", "checkbox-blank-circle-outline"),
               "lightbulb": ("lightbulb", "lightbulb-outline"), "drop": ("water", "water-outline")}


def level_icon(h, full):
    return LEVEL_ICONS.get(h.cfg["level_icon"], LEVEL_ICONS["heart"])[0 if full else 1]


def slider(h, dev, back, color, cls="hearts slider", style=""):
    """Brightness as a slider: a track filled up to the level, a knob, and 10 tap zones (10-100 %)."""
    pct = (dev["pct"] or 0) if dev["on"] else 0
    knob = (f'<span class="knob" style="left:{pct}%">{h.icon(level_icon(h, True), "000" if color == "fff" else "fff", "")}</span>'
            if dev["on"] else "")
    zones = "".join(form(h, "level", dev["eid"], back, "", "seg", f' style="left:{i * 10}%;width:10%"', value=lvl)
                    for i, lvl in enumerate(range(10, 101, 10)))
    return (f'<div class="{cls}"{style}><span class="trk"><span class="fill" style="width:{pct}%"></span></span>'
            f'{knob}{zones}</div>')


def hearts(h, dev, back, color):
    if not dev["dimmable"]:
        return ""
    if h.cfg["level_style"] == "slider":
        return slider(h, dev, back, color)
    pct = dev["pct"] or 0
    w = 100 / len(h.levels)
    cells = ""
    for i, lvl in enumerate(h.levels):
        full = dev["on"] and pct >= lvl - 10
        cells += form(h, "level", dev["eid"], back, h.icon(level_icon(h, full), color, ""),
                      "seg", f' style="left:{i * w:.3f}%;width:{w:.3f}%"', value=lvl)
    return f'<div class="hearts">{cells}</div>'


CONTROL_ICONS = {"open": "arrow-up", "close": "arrow-down", "stop": "stop", "lock": "lock",
                 "unlock": "lock-open-variant", "playpause": "play-pause", "volup": "volume-plus",
                 "voldown": "volume-minus", "warmer": "plus", "cooler": "minus", "start": "play",
                 "dock": "home-import-outline"}


def controls(h, dev, back, color):
    acts = dev["controls"]
    if not acts:
        return ""
    w = 100 / len(acts)
    return '<div class="ctl">' + "".join(
        form(h, a, dev["eid"], back, f'<span>{h.icon(CONTROL_ICONS[a], color, "")}</span>', "seg",
             f' style="left:{i * w:.3f}%;width:{w:.3f}%"') for i, a in enumerate(acts)) + "</div>"


def device_href(h, dev, back):
    return f'/device/{h.quote(dev["eid"])}?b={h.quote(back)}'


def device_card(h, dev, back, cls, style):
    """A device card: tap toggles/runs; dimmable lights get hearts, covers/media/climate get round buttons.
    Devices that can do more (colours, modes, extra buttons, ...) get a round "..." to their own page;
    if tapping can't toggle them (climate), the whole card opens that page."""
    color = "fff" if dev["on"] else ("888" if dev["na"] else "000")
    state = " on" if dev["on"] else (" na" if dev["na"] else "") + (" info" if dev["info"] else "")
    extra = " dim" if dev["dimmable"] else (" hasctl" if dev["controls"] else "")
    page = dev.get("page")
    paw = "" if page else h.icon("paw", color, "paw")
    inner = (f'{paw}{h.icon(dev["icon"], color, "big")}'
             f'<span class="nm">{h.esc(dev["name"])}</span><span class="st">'
             f'{h.icon(dev["mode_icon"], color, "mi") if dev.get("mode_icon") else ""}{h.esc(dev["state"])}</span>')
    if dev["main"]:
        main = form(h, dev["main"], dev["eid"], back, inner, "hit")
    elif page:
        main = f'<a class="hit" href="{device_href(h, dev, back)}">{inner}</a>'
    else:
        main = f'<div class="hit">{inner}</div>'
    more = f'<a class="more" href="{device_href(h, dev, back)}">{h.icon("dots-horizontal")}</a>' if page else ""
    return (f'<div class="card {cls}{state}{extra}{" pg" if more else ""}" data-eid="{h.esc(dev["eid"])}"{style}>{corners()}{main}{hearts(h, dev, back, color)}'
            f'{controls(h, dev, back, color)}{more}</div>')


def pager(h, page, pages, base):
    if pages <= 1:
        return ""
    base += "&" if "?" in base else "?"
    prev = (f'<a href="{base}p={page - 1}">{h.icon("chevron-left")}</a>' if page > 1
            else f'<span class="dis">{h.icon("chevron-left", "bbb")}</span>')
    nxt = (f'<a href="{base}p={page + 1}">{h.icon("chevron-right")}</a>' if page < pages
           else f'<span class="dis">{h.icon("chevron-right", "bbb")}</span>')
    return f'<div class="pager">{prev}<b>{page}/{pages}</b>{nxt}</div>'


def page_slice(items, page, per=PER_PAGE):
    pages = max(1, math.ceil(len(items) / per))
    page = min(max(page, 1), pages)
    return items[(page - 1) * per:page * per], page, pages


def uv_word(uv):
    if uv is None:
        return "–"
    return "low" if uv < 3 else "moderate" if uv < 6 else "high" if uv < 8 else "very high" if uv < 11 else "extreme"


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# --- the cat --------------------------------------------------------------------------------

def cat_says(d):
    """(prop icon, message, face) - what the cat says right now. Varies by the minute between fitting lines."""
    cat, you = d["cat"], d["you"]
    hi = f", {you}" if you else ""
    w, hour = d.get("weather"), d["now"].hour
    on = [x for x in d.get("devices", []) if x["on"]]
    night = d["sun"]["is_night"]
    pools = []
    kinds_on = {x.get("kind") for x in on}
    if d.get("moved"):
        pools.append(("map-marker-outline", [f"Hello from the {d['room']}!", f"{cat} followed me to the {d['room']}",
                                             f"Visiting the {d['room']} today"], "(=^o^=)"))
    if d.get("festive"):
        pools.append(("string-lights", ["Twinkle twinkle! The fairy lights are on", f"{cat} is batting at the twinkly lights",
                                        "So sparkly in here!"], "(=^.^=) *"))
    if d.get("deco") == "snow" and d["now"].month == 12 and d["now"].day < 25:
        n = 25 - d["now"].day
        pools.append(("gift-outline", [f"Only {plural(n, 'sleep')} until Christmas!", f"{cat} wants a present too"],
                      "(=^.^=)"))
    if d.get("deco") == "pumpkin":
        pools.append(("ghost", ["Boo! Happy Halloween", f"{cat} is dressed as a tiny pumpkin"], "(=^o^=)"))
    bins = (d.get("bins") or {}).get("tomorrow")
    if bins and hour >= 16:
        what = " + ".join(b["name"] for b in bins)
        pools.append((bins[0]["icon"], [f"{what} goes out tonight!", f"Bin night! {cat} will guard the {what}"],
                      "(=^o^=)"))
    if "tv" in kinds_on:
        pools.append(("popcorn", [f"Movie time? {cat} saved you a spot", "Popcorn ready?"], "(=^.^=)"))
    if any(x["domain"] == "climate" and x["raw"] == "heat" for x in on):
        pools.append(("fire", [f"Heating's on, toasty toes{hi}!", f"{cat} found the warm spot"], "(=^.^=)"))
    if any(x["domain"] == "climate" and x["raw"] in ("cool", "dry") for x in on) or any(
            x.get("kind") == "ac" and x["domain"] != "climate" for x in on):
        pools.append(("snowflake", ["Ahh, nice and cool in here", f"{cat} is sitting right in the breeze"], "(=-.-=)"))
    ind = d.get("indoor")
    if ind and ind["raw"] < 18:
        pools.append(("thermometer-low", [f"Brr, only {ind['temp']}° inside. Blanket time{hi}?",
                                          f"{cat} is curled up extra tight"], "(=;.;=)"))
    elif ind and ind["raw"] > 26:
        pools.append(("thermometer-high", [f"Toasty! {ind['temp']}° inside", f"{cat} is stretched out on the cool tiles"],
                      "(=-.-=)"))
    if w and w["state"] in ("rainy", "pouring", "lightning-rainy", "snowy", "snowy-rainy", "hail"):
        pools.append(("umbrella-outline", [f"{w['now_text']} outside! Perfect for tea and a blanket",
                                           f"{cat} is watching the {'snow' if 'snow' in w['state'] else 'rain'} from the window"],
                      "(=^.^=)"))
    if w and isinstance(w.get("raw_temp"), (int, float)) and w["raw_temp"] <= 3:
        pools.append(("snowflake", [f"Brr, only {w['temp']}° outside! Stay warm{hi}",
                                    f"{cat} found the warmest spot in the house"], "(=^.^=)"))
    if w and isinstance(w.get("raw_temp"), (int, float)) and w["raw_temp"] >= 26:
        pools.append(("fan", [f"Phew, {w['temp']}°! Drink some water{hi}", f"{cat} is lying flat on the cool floor"],
                      "(=-.-=)"))
    if w and not night and (w.get("uv_now") or 0) >= 6:
        pools.append(("sunglasses", [f"UV is {uv_word(w['uv_now'])} today, don't forget sunscreen!"], "(=^.^=)"))
    if 5 <= hour < 11:
        pools.append(("coffee", [f"Good morning{hi}! Rise and shine", f"{cat} wants breakfast... and so do you?",
                                 "A fresh new day, let's make it a nice one"], "(=^o^=)"))
    elif night and on:
        pools.append(("heart", [f"Cozy lights on! Time to snuggle{hi}", f"{cat} is curled up on the sofa",
                                "Soft lights, warm home. Purrfect"], "(=^.^=) <3"))
    elif night:
        pools.append(("sleep", ["All dark... sweet dreams", f"{cat} is fast asleep. Shhh", "Good night, little home"],
                      "(=-.-=) zzz"))
    elif on:
        pools.append(("heart", [f"Hi{hi}! {on[0]['name']} is on, so cosy in here", f"{cat} approves of the lighting"],
                      "(=^.^=)"))
    else:
        pools.append(("flower-outline", [f"Good {'afternoon' if hour < 18 else 'evening'}{hi}! All is calm at home",
                                         f"{cat} is purring. Everything's fine", "Nice day? Lights are off"],
                      "(=^.^=)"))
    prop, lines, face = pools[d["now"].minute // 5 % len(pools)]
    return prop, lines[d["now"].minute % len(lines)], face


# --- Home ---------------------------------------------------------------------------------------

SM_CSS = """
/* compact cards (3-4 on Home, 3 rows on a room page): icon left. Must come after the other card rules. */
.card.sm .big{left:16px;top:50%;width:52px;height:52px;margin:-26px 0 0 0}
.card.sm .nm{left:80px;right:10px;top:50%;margin-top:-25px;text-align:left;font-size:20px}
.card.sm .st{left:80px;right:10px;top:50%;margin-top:3px;text-align:left;font-size:14px}
.card.sm.dim .hit,.card.sm.hasctl .hit{bottom:42%}
.card.sm.dim .big,.card.sm.hasctl .big{top:14px;width:52px;height:52px;margin:0;left:16px}
.card.sm.dim .nm,.card.sm.hasctl .nm{top:16px;margin-top:0}.card.sm.dim .st,.card.sm.hasctl .st{top:44px;margin-top:0}
.card.sm .hearts,.card.sm .ctl{height:40%;bottom:2%}
.card.sm .hearts img{width:26px;height:26px;margin:-13px 0 0 -13px}
.card.sm .paw{display:none}
.card.sm.info .st{left:80px;right:10px;top:50%;margin-top:-28px;text-align:left;font-size:24px;font-weight:900}
.card.sm.info .nm{left:80px;right:10px;top:50%;margin-top:4px;text-align:left;font-size:13px;font-weight:700}
.card.sm.info .big{width:44px;height:44px;margin-top:-22px;left:20px}
.card.sm.pg .nm,.card.sm.pg .st{right:52px}
.card.sm a.more{top:50%;margin-top:-21px}
.card.sm.dim a.more,.card.sm.hasctl a.more{top:14px;margin-top:0}
.card.xs .big{width:44px;height:44px;margin-top:-22px;left:14px}
.card.xs .nm{left:68px;font-size:18px;margin-top:-23px}.card.xs .st{left:68px;font-size:13px;margin-top:2px}
.card.xs.dim .big,.card.xs.hasctl .big{width:40px;height:40px;top:13px;margin-top:0;left:14px}
.card.xs.dim .nm,.card.xs.hasctl .nm{top:13px;margin-top:0}.card.xs.dim .st,.card.xs.hasctl .st{top:38px;margin-top:0}
.card.xs.dim a.more,.card.xs.hasctl a.more{top:11px}
.card.xs .hearts img{width:24px;height:24px;margin:-12px 0 0 -12px}
.card.xs .ctl .seg span{width:38px;height:38px;margin:-19px 0 0 -19px;border-radius:19px}
.card.xs .ctl .seg img{width:22px;height:22px;margin-top:5px}
"""

HOME_CSS = """
.card.sm.wide .big{left:30%}.card.sm.wide .nm,.card.sm.wide .st{left:30%;margin-left:70px}
.card.sm.wide.dim .big,.card.sm.wide.hasctl .big{left:16px}
.card.sm.wide.dim .nm,.card.sm.wide.dim .st,.card.sm.wide.hasctl .nm,.card.sm.wide.hasctl .st{left:80px;margin-left:0}
.card .st img.mi{width:16px;height:16px;vertical-align:-3px;margin-right:4px}
.hello{left:4%;right:4%;top:2%;height:25%;border:3px dashed #000;}
.hello .cat{position:absolute;left:5%;top:50%;width:112px;height:112px;margin-top:-58px}
.hello .prop{position:absolute;left:25%;top:12%;width:30px;height:30px}
.bubble{position:absolute;left:37%;right:4%;top:13%;bottom:13%;border:3px solid #000;background:#fff}
.bubble .tl{position:absolute;left:-14px;top:50%;margin-top:-10px;width:0;height:0;border-top:10px solid transparent;
  border-bottom:10px solid transparent;border-right:14px solid #000}
.bubble .tx{position:absolute;left:9%;right:7%;top:50%;-webkit-transform:translateY(-50%);transform:translateY(-50%);
  font-size:18px;font-weight:800;line-height:1.25}
.bubble .face{font-size:14px;font-weight:700;color:#555;display:block;margin-top:4px}
.ttime{left:5%;top:29%;font-size:50px;font-weight:900;line-height:1}
.tdate{left:5.4%;top:37.6%;font-size:15px;font-weight:800;color:#444;white-space:nowrap}
.tdate .in{margin-left:8px;color:#000;font-weight:900}
.tdate .in img{width:18px;height:18px;vertical-align:-3px;margin-right:2px}
.moved{left:38%;top:0.2%;height:26px;line-height:26px;padding:0 10px 0 6px;background:#000;color:#fff;border-radius:13px;
  font-size:13px;font-weight:900;white-space:nowrap}
.moved img{width:16px;height:16px;vertical-align:-3px;margin-right:3px}
.deco{position:absolute;background:#fff;border-radius:50%}
.deco img{width:100%;height:100%;display:block}
.stick{right:4%;top:29%;height:12%;width:48%;background:#000;color:#fff;display:block}
.stick img{position:absolute;left:12px;top:50%;width:42px;height:42px;margin-top:-21px}
.stick .a{position:absolute;left:62px;right:8px;top:50%;margin-top:-23px;font-size:20px;font-weight:900;line-height:24px;white-space:nowrap;overflow:hidden}
.stick .b{position:absolute;left:62px;right:8px;top:50%;margin-top:3px;font-size:13px;font-weight:700;white-space:nowrap;overflow:hidden}
.card .big{position:absolute;left:50%;top:13%;width:84px;height:84px;margin-left:-42px}
.card .nm{position:absolute;left:4%;right:4%;top:50%;font-size:23px;font-weight:900;white-space:nowrap;overflow:hidden}
.card .st{position:absolute;left:4%;right:4%;top:63%;font-size:15px;font-weight:700;white-space:nowrap;overflow:hidden}
.card.dim .hit,.card.hasctl .hit{bottom:24%}
.card.dim .big,.card.hasctl .big{top:10%}
.card.dim .nm,.card.hasctl .nm{top:56%}.card.dim .st,.card.hasctl .st{top:73%}
.scenes{left:4%;right:4%;top:87.5%;height:10%}
.scenes form{position:absolute;top:50%;margin-top:-25px;height:50px;border:3px solid #000;background:#fff;box-sizing:border-box;-webkit-box-sizing:border-box}
.scenes button{font-size:16px;font-weight:900;white-space:nowrap;overflow:hidden;padding:0 8px}
.scenes img{width:22px;height:22px;vertical-align:-5px;margin-right:5px}
.foot{left:0;right:0;bottom:1.8%;text-align:center;font-size:15px;font-weight:800}
.foot img{width:18px;height:18px;vertical-align:-4px;margin:0 4px}
.empty{left:8%;right:8%;top:50%;text-align:center;font-size:17px;font-weight:800;color:#555}
""" + SM_CSS


DECO_ICONS = {"snow": ["snowflake", "snowflake-variant", "snowflake", "snowflake-variant", "snowflake"],
              "pumpkin": ["halloween", "ghost", "halloween", "ghost", "halloween"],
              "festive": ["string-lights", "star", "string-lights", "star", "star-outline"]}


def decorations(h, d, spots):
    """Seasonal icons in the free spots between the boxes on Home: [(left %, top %, size px)]."""
    kind = "festive" if d.get("festive") else d.get("deco")
    if not kind:
        return ""
    return "".join(f'<span class="deco" style="left:{x}%;top:{y}%;width:{sz}px;height:{sz}px">'
                   f'{h.icon(DECO_ICONS[kind][i], "000", "")}</span>' for i, (x, y, sz) in enumerate(spots))


def home_page(h, d):
    w = d["weather"]
    prop, msg, face = cat_says(d)
    back = "/"
    devs = d["devices"][:6]
    compact = len(devs) > 4
    parts = h.cfg["home_parts"]
    date = h.esc(d["date"])
    ind = d.get("indoor") if "indoor" in parts else None
    if ind:
        hum = f' · {ind["hum"]}%' if ind.get("hum") else ""
        date = (f'{h.esc(d["now"].strftime("%a %-d %b"))}<span class="in">{h.icon("home-thermometer-outline")}'
                f'{ind["temp"]}°{hum}</span>')
    out = ""
    if h.cfg["hello_size"] != "off":
        out += (f'<div class="abs hello dash">{corners(30)}{h.icon(h.pet["icon"], "000", "cat")}{h.icon(prop, "000", "prop")}'
                f'<div class="bubble">{corners(22)}<span class="tl"></span><div class="tx">{h.esc(msg)}'
                f'<span class="face">{h.esc(face)}</span></div></div></div>')
    out += (f'<div class="abs ttime">{d["time"]}</div><div class="abs tdate">{date}</div>')
    if d.get("moved"):
        out += f'<div class="abs moved">{h.icon("map-marker-outline", "fff")}{h.esc(d["room"])}</div>'
    w = w if "weather" in parts else None
    if w:
        out += (f'<a class="abs stick nob dark" href="/weather">{corners(24)}{h.icon(w["icon"], "fff")}'
                f'<span class="a">{w["temp"]}° {h.esc(w["now_text"])}</span>'
                f'<span class="b">UV {h.esc(uv_word(w["uv"]))} · {w["hi"]}°/{w["lo"]}° {h.esc(w["day_label"].lower())}</span></a>')
    bins = d.get("bins") if "bins" in parts else None
    if bins is not None:
        if bins["tomorrow"]:
            names = " + ".join(h.esc(b["name"]) for b in bins["tomorrow"])
            out += (f'<div class="abs bins">{"".join(h.icon(b["icon"], "fff") for b in bins["tomorrow"][:3])}'
                    f'<b>{names}</b> tomorrow</div>')
        else:
            out += f'<div class="abs bins none">{h.icon("delete-empty-outline", "888")}no bins tomorrow</div>'
    rows = 1 if len(devs) <= 2 else 2 if len(devs) <= 4 else 3
    layout_css, top, spots = home_layout(rows, bool(w), bins is not None, h.cfg["hello_size"])
    bottom = 86 if d["scenes"] else 92 if "moon" in parts else 97
    if not devs and d.get("moved"):
        out += (f'<div class="abs empty">Nothing to switch in the {h.esc(d["room"])} yet. (=^.^=)<br>'
                f'Settings &gt; Move kiosk takes me back to the {h.esc(d["main_room"])}.</div>')
    elif not devs:
        out += ('<div class="abs empty">No devices yet. Pick some for this screen on your computer:<br>'
                '<b>Settings</b> tells you where.</div>')
    elif len(devs) <= 2:
        for i, dev in enumerate(devs):
            left = 4 + i * 47 if len(devs) == 2 else 26
            out += device_card(h, dev, back, "",
                               f' style="left:{left}%;width:45%;top:{top}%;height:{bottom - top}%"')
    else:
        rh = (bottom - top - 2 * (rows - 1)) / rows
        for i, dev in enumerate(devs):
            wide = i == len(devs) - 1 and len(devs) % 2   # an odd last card fills its row
            out += device_card(h, dev, back, ("sm xs" if compact else "sm") + (" wide" if wide else ""),
                               f' style="left:{4 + (i % 2) * 47}%;width:{92 if wide else 45}%;'
                               f'top:{top + (i // 2) * (rh + 2):.2f}%;height:{rh:.2f}%"')
    if d["scenes"]:
        w_ = 100 / len(d["scenes"])
        out += '<div class="abs scenes">' + "".join(
            form(h, sc["main"] or "run", sc["eid"], back, f'{h.icon(sc["icon"])}{h.esc(sc["name"])}', "",
                 f' style="left:{i * w_ + 1:.2f}%;width:{w_ - 2:.2f}%"', r=24) for i, sc in enumerate(d["scenes"])) + "</div>"
    elif "moon" in parts:
        out += (f'<div class="abs foot">{h.icon("heart")}{h.esc(d["moon"]["name"].lower())} tonight'
                f'{h.icon(d["moon"]["icon"])}· {h.esc(d["sun"]["label"].lower())} {d["sun"]["time"]}</div>')
    out += decorations(h, d, spots)
    return shell(h, "Home", HOME_CSS + BINS_CSS + layout_css, out, "home", d["refresh"], d["live"])


# Bin day pill under the weather stick (only with the Afvalbeheer integration in HA); placed by home_layout
BINS_CSS = """
.bins{right:4%;width:48%;padding:0 10px;box-sizing:border-box;-webkit-box-sizing:border-box;border-radius:15px;
background:#000;color:#fff;font-size:14px;font-weight:700;white-space:nowrap;overflow:hidden;text-align:center}
.bins b{font-weight:900;font-size:15px}
.bins img{width:18px;height:18px;vertical-align:-4px;margin-right:4px}
.bins.none{background:#fff;color:#999;border:2px dashed #bbb}
"""

PAGE_PX = 680   # height of #page in CSS px on the Kindle (756 - the tab bar)
# Home by rows of cards: the more rows, the smaller the cat box, so the cards keep room.
#   rows: (cat box %, cat px, prop (left %, top %, px), bubble left %, bubble inset %, text px, clock px,
#          weather px with bins, weather px without)
HOME_TIERS = {1: (25, 112, (25, 12, 30), 37, 13, 18, 50, 66, 74),
              2: (19.5, 92, (22, 10, 26), 33, 11, 17, 46, 62, 72),
              3: (14, 70, (18, 52, 22), 28, 8, 16, 42, 58, 64)}
BIN_PX, BIN_GAP = 28, 10


HELLO_TIERS = {"large": 1, "medium": 2, "small": 3}


def home_layout(rows, weather, bins, hello_size="auto"):
    """(css, top % of the cards, decoration spots) for Home with this many rows of cards. hello_size: the pet's
    box (auto: smaller with more rows; large/medium/small; off: no box)."""
    hello, cat, (px, py, ps), bl, inset, tx, _, _, _ = HOME_TIERS[HELLO_TIERS.get(hello_size, rows)]
    clock, w_bins, w_plain = HOME_TIERS[rows][6:]
    pct = lambda v: v * 100 / PAGE_PX
    y = 2 if hello_size == "off" else 2 + hello + 2     # the clock/weather row starts under the pet's box
    stick = (w_bins if bins else w_plain) if weather else 0
    right = stick + (BIN_PX + (BIN_GAP if weather else 0) if bins else 0)
    block = clock + 8 + 18                              # clock + date line
    row = pct(max(right, block))
    t = y + max(0, (row - pct(block)) / 2)
    css = (f".hello{{height:{hello}%}}"
           f".hello .cat{{width:{cat}px;height:{cat}px;margin-top:-{cat // 2 + 2}px;left:{5 if cat > 100 else 4}%}}"
           f".hello .prop{{left:{px}%;top:{py}%;width:{ps}px;height:{ps}px}}"
           f".bubble{{left:{bl}%;top:{inset}%;bottom:{inset}%}}.bubble .tx{{font-size:{tx}px}}"
           f".ttime{{top:{t:.2f}%;font-size:{clock}px}}.tdate{{top:{t + pct(clock + 8):.2f}%}}"
           f".stick{{top:{y}%;height:{pct(stick):.2f}%}}")
    if hello < 15:
        css += ".bubble .face{display:inline;margin:0 0 0 6px}.bubble .tx{line-height:1.2}"
    if rows == 3:
        css += ".stick img{width:36px;height:36px;margin-top:-18px}.stick .a{left:56px}.stick .b{left:56px}"
    if bins:
        css += (f".bins{{top:{y + pct(stick + (BIN_GAP if weather else 0)):.2f}%;height:{BIN_PX}px;line-height:{BIN_PX}px}}"
                f".bins.none{{line-height:{BIN_PX - 4}px}}")
    spots = [] if hello_size == "off" else [(19, 0.6, 20), (78, 0.6, 22)]
    spots += [(33, y + 1.2, 22), (43, y + pct(clock) * 0.8, 16)]
    if row > 12:
        spots.append((44, y + row - 2.6, 14))
    return css, y + row + 2.5, spots


# --- Rooms --------------------------------------------------------------------------------------

ROOMS_CSS = """
.room{display:block}
.room .ring{position:absolute;left:16px;top:16px;width:62px;height:62px;border-radius:31px;background:#eee}
.room.on .ring{background:#fff}
.room .ring img{width:38px;height:38px;margin:12px 0 0 12px}
.room .nm{position:absolute;left:18px;right:12px;bottom:40px;font-size:24px;font-weight:900;white-space:nowrap;overflow:hidden}
.room .st{position:absolute;left:18px;right:12px;bottom:16px;font-size:15px;font-weight:700;white-space:nowrap;overflow:hidden}
.room .st img{width:16px;height:16px;vertical-align:-3px;margin-right:4px}
.room .paw{width:22px;height:22px;right:14px;top:14px}
.tip{left:4%;right:40%;bottom:3%;height:8%;font-size:14px;font-weight:800;color:#555}
.tip img{width:20px;height:20px;vertical-align:-4px;margin-right:4px}
"""


def rooms_page(h, d, page_no=1):
    shown, page_no, pages = page_slice(d["rooms"], page_no)
    lit = d["lights_on"]
    sub = (plural(lit, "light") + " on") if lit else "all cosy & dark"
    out = header(h, d, "Rooms", "home-group", sub)
    rows = 3
    for i, r in enumerate(shown):
        on = r["lit"] > 0
        color = "fff" if on else "000"
        if r["lit"]:
            st = f'{h.icon("heart", color)}{plural(r["lit"], "light")} on'
        elif r["lights"]:
            st = "Lights off"
        else:
            st = plural(r["devices"], "device") if r["devices"] else plural(r["sensors"], "sensor")
        if r.get("temp"):
            st += f' · {h.icon(r["climate"], color) if r.get("climate") else ""}{r["temp"]}°'
        mark = h.icon("map-marker", color, "paw") if r.get("here") else h.icon("paw", color, "paw")
        top = 14 + (i // 2) * (72 / rows)
        out += (f'<a class="card room{" on" if on else ""}" href="/room/{h.quote(r["id"])}" '
                f'style="left:{4 + (i % 2) * 47}%;width:45%;top:{top:.2f}%;height:{72 / rows - 2:.2f}%">'
                f'{corners()}<span class="ring">{h.icon(r["icon"])}</span>{mark}'
                f'<span class="nm">{h.esc(r["name"])}</span><span class="st">{st}</span></a>')
    out += '<div class="abs strip">' + pager(h, page_no, pages, "/rooms")
    if pages <= 1:
        out += f'<div class="abs tip" style="left:0;bottom:auto;top:30%">{h.icon(h.pet["icon"], "555")}Tap a room to peek inside</div>'
    if lit:
        out += form(h, "alloff", "all", f"/rooms?p={page_no}", f'{h.icon("lightbulb-group-off", "fff")}All lights off',
                    "pill", ' style="right:0"')
    out += "</div>"
    return shell(h, "Rooms", ROOMS_CSS, out, "rooms", d["refresh"], d["live"])


# --- One room -----------------------------------------------------------------------------------

ROOM_CSS = HOME_CSS + """
.card .big{width:64px;height:64px;margin-left:-32px;top:12%}
.card .nm{font-size:20px;top:52%}
.card .st{font-size:14px;top:67%}
.card.dim .big,.card.hasctl .big{width:52px;height:52px;margin-left:-26px;top:8%}
.card.dim .nm,.card.hasctl .nm{top:44%}.card.dim .st,.card.hasctl .st{top:60%}
.card .hearts img{width:26px;height:26px;margin:-13px 0 0 -13px}
.card.dim .hit,.card.hasctl .hit{bottom:26%}
.card.info .big{width:40px;height:40px;margin-left:-20px;top:12%}
.card.info .st{top:40%;font-size:26px;font-weight:900}
.card.info .nm{top:66%;font-size:15px;font-weight:700}
.stk{position:absolute;top:8%;bottom:8%;border:3px dashed #000;text-align:center;}
.stk .v{display:block;font-size:17px;font-weight:900;margin-top:4px;white-space:nowrap}
.stk .v img{width:22px;height:22px;vertical-align:-5px;margin-right:3px}
.stk .l{display:block;font-size:11px;font-weight:800;color:#555;white-space:nowrap;overflow:hidden;padding:0 4px}
""" + SM_CSS


def room_page(h, d, page_no=1):
    ents = d["entities"]
    sensors = [e for e in ents if e["info"]]
    devices = [e for e in ents if not e["info"]]
    room_off = d["lit"] > 0 and not d["other"]
    max_stickers = 3 if room_off else 4
    if len(devices) + len(sensors) <= PER_PAGE:      # everything fits: sensors become cards too
        stickers = []
    else:
        stickers = sensors if len(sensors) <= max_stickers else []
    tiles = devices + [e for e in sensors if e not in stickers]
    shown, page_no, pages = page_slice(tiles, page_no)
    if pages > 1:   # the strip is needed for the pager: show the stickers as cards instead
        tiles, stickers = devices + sensors, []
        shown, page_no, pages = page_slice(tiles, page_no)
    base = f'/room/{h.quote(d["id"])}'
    back = f"{base}?p={page_no}"
    sub = (plural(d["lit"], "light") + " on") if d["lit"] else ("all dark" if any(e["domain"] == "light" for e in ents)
                                                               else plural(len(devices), "device"))
    out = header(h, d, d["name"], d["icon"], sub, back="/rooms")
    n = len(shown)
    rows = 2 if n <= 4 else 3
    top0, span = 13.5, 74
    rh = span / rows
    for i, e in enumerate(shown):
        out += device_card(h, e, back, "sm" if rows == 3 else "", f' style="left:{4 + (i % 2) * 47}%;width:45%;'
                                           f'top:{top0 + (i // 2) * rh:.2f}%;height:{rh - 2:.2f}%"')
    if not shown:
        out += '<div class="abs empty">Nothing here yet. (=^.^=)</div>'
    out += '<div class="abs strip">'
    if pages > 1:
        out += pager(h, page_no, pages, base)
    elif stickers:
        width = 62 if room_off else 100
        sw = width / len(stickers)
        out += "".join(f'<div class="stk dash" style="left:{i * sw + 0.5:.2f}%;width:{sw - 1:.2f}%">{corners(20)}'
                       f'<span class="v">{h.icon(s["icon"])}{h.esc(s["state"])}</span>'
                       f'<span class="l">{h.esc(s["name"])}</span></div>' for i, s in enumerate(stickers))
    if room_off:
        out += form(h, "alloff", d["id"], back, f'{h.icon("lightbulb-group-off", "fff")}All off', "pill", ' style="right:0"')
    out += "</div>"
    return shell(h, d["name"], ROOM_CSS, out, "rooms", d["refresh"], d["live"])


# --- Weather ------------------------------------------------------------------------------------

WEATHER_CSS = """
.hero{left:4%;right:4%;top:13%;height:25%;border:3px dashed #000;}
.hero .ring{position:absolute;left:4%;top:50%;width:124px;height:124px;margin-top:-62px;border-radius:62px;background:#000}
.hero .ring img{width:84px;height:84px;margin:20px 0 0 20px}
.hero .t{position:absolute;left:34%;top:9%;font-size:66px;font-weight:900;line-height:1}
.hero .c{position:absolute;left:34.5%;top:45%;font-size:20px;font-weight:900}
.hero .hl{position:absolute;left:34.5%;top:62%;font-size:15px;font-weight:800;color:#444}
.hero .say{position:absolute;left:34.5%;right:4%;top:78%;font-size:14px;font-weight:800;white-space:nowrap;overflow:hidden}
.hero .say img{width:18px;height:18px;vertical-align:-4px;margin-right:4px}
.facts{left:4%;right:4%;top:40%;height:10.5%}
.fact{position:absolute;top:0;bottom:0;border:3px solid #000;text-align:center}
.fact img{width:24px;height:24px;display:block;margin:6px auto 0}
.fact b{display:block;font-size:17px;font-weight:900;line-height:20px}
.fact span{display:block;font-size:11px;font-weight:800;color:#555}
.hours{left:4%;right:4%;top:52.5%;height:16%;background:#000;color:#fff;}
.hr{position:absolute;top:0;bottom:0;text-align:center}
.hr .h{display:block;font-size:13px;font-weight:800;margin-top:10px}
.hr img{width:34px;height:34px;display:block;margin:4px auto}
.hr .v{display:block;font-size:17px;font-weight:900}
.days{left:4%;right:4%;top:70.5%;height:16%}
.day{position:absolute;top:0;bottom:0;text-align:center}
.day .in{position:absolute;left:4px;right:4px;top:0;bottom:0;border:3px dashed #000;}
.day .n{display:block;font-size:14px;font-weight:900;margin-top:7px}
.day img{width:32px;height:32px;display:block;margin:3px auto}
.day .v{display:block;font-size:14px;font-weight:800}
.sunrow{left:4%;right:4%;top:88.5%;height:9%;font-size:15px;font-weight:900;text-align:center}
.sunrow span{display:inline-block;margin:0 8px;white-space:nowrap}
.sunrow img{width:24px;height:24px;vertical-align:-6px;margin-right:5px}
"""


def weather_quip(d):
    w = d["weather"]
    t = w.get("raw_temp")
    if w["state"] in ("rainy", "pouring", "lightning-rainy"):
        return "umbrella-outline", "Take an umbrella!"
    if w["state"] in ("snowy", "snowy-rainy", "hail"):
        return "snowflake", "Snow day! Mittens on"
    if isinstance(t, (int, float)) and t <= 5:
        return "thermometer-low", "Brr! Wear a warm scarf"
    if (w.get("uv") or 0) >= 6:
        return "sunglasses", "Sunscreen weather!"
    if isinstance(t, (int, float)) and t >= 25:
        return "ice-cream", "Ice cream weather!"
    return "@pet", f"{d['cat']} says: lovely out there"



def weather_page(h, d):
    w = d["weather"]
    if not w:
        out = header(h, d, "Weather", "weather-partly-cloudy") + \
            '<div class="abs empty">No weather in Home Assistant yet. (=;.;=)</div>'
        return shell(h, "Weather", HOME_CSS + WEATHER_CSS, out, "weather", d["refresh"], d["live"])
    qi, qt = weather_quip(d)
    qi = h.pet["icon"] if qi == "@pet" else qi
    out = header(h, d, "Weather", "weather-partly-cloudy", w["now_text"])
    out += (f'<div class="abs hero dash">{corners(30)}<div class="ring">{h.icon(w["icon"], "fff", "", big=True)}</div>'
            f'<div class="t">{w["temp"]}°</div><div class="c">{h.esc(w["now_text"])}</div>'
            f'<div class="hl">{h.esc(w["day_label"])}: {w["hi"]}° / {w["lo"]}° · {h.esc(w["day_cond"].lower())}</div>'
            f'<div class="say">{h.icon(qi)}{h.esc(qt)}</div></div>')
    facts = [("sun-wireless-outline", f'{w["uv"] if w["uv"] is not None else "–"}', f'UV {uv_word(w["uv"])}'),
             ("umbrella-outline", f'{w["rain"]} mm', "rain"), ("weather-windy", f'{w["wind"]}', "km/h wind"),
             ("water-percent", f'{w["humidity"]}%', "humidity")]
    if d.get("indoor"):
        facts.append(("home-thermometer-outline", f'{d["indoor"]["temp"]}°', "inside"))
    fw = 100 / len(facts)
    out += '<div class="abs facts">' + "".join(
        f'<div class="fact" style="left:{i * fw + 0.6:.2f}%;width:{fw - 1.2:.2f}%">{corners(20)}{h.icon(ic)}<b>{h.esc(v)}</b>'
        f'<span>{h.esc(l)}</span></div>' for i, (ic, v, l) in enumerate(facts)) + "</div>"
    hours = w["hours"][:7]
    if hours:
        cw = 100 / len(hours)
        out += f'<div class="abs hours nob dark">{corners(26)}' + "".join(
            f'<div class="hr" style="left:{i * cw:.3f}%;width:{cw:.3f}%"><span class="h">{"now" if i == 0 else x["t"]}</span>'
            f'{h.icon(x["icon"], "fff")}<span class="v">{x["temp"]}°</span></div>' for i, x in enumerate(hours)) + "</div>"
    days = w["days"][:5]
    if days:
        cw = 100 / len(days)
        out += '<div class="abs days">' + "".join(
            f'<div class="day" style="left:{i * cw:.3f}%;width:{cw:.3f}%"><div class="in dash">{corners(20)}<span class="n">{x["day"]}</span>'
            f'{h.icon(x["icon"])}<span class="v">{x["hi"]}°/{x["lo"]}°</span></div></div>' for i, x in enumerate(days)) + "</div>"
    s = d["sun"]
    out += (f'<div class="abs sunrow"><span>{h.icon("weather-sunset-up")}{s["rise"]}</span>'
            f'<span>{h.icon("weather-sunset-down")}{s["set"]}</span>'
            f'<span>{h.icon(d["moon"]["icon"])}{h.esc(d["moon"]["name"].lower())}</span></div>')
    return shell(h, "Weather", HOME_CSS + WEATHER_CSS, out, "weather", d["refresh"], d["live"])


# --- Lights -------------------------------------------------------------------------------------

LIGHTS_CSS = ROOM_CSS + """
.sec{left:4%;right:4%;height:7%;font-size:18px;font-weight:900;line-height:50px;white-space:nowrap}
.sec img{width:26px;height:26px;vertical-align:-6px;margin-right:6px}
.sec small{font-size:13px;font-weight:800;color:#555;margin-left:6px}
.sec .pill{right:0;top:50%}
.sw{position:absolute;right:0;top:50%;margin-top:-22px;height:44px;white-space:nowrap}
.sw a{display:inline-block;height:44px;line-height:38px;padding:0 14px;border:3px solid #000;border-radius:22px;
  box-sizing:border-box;-webkit-box-sizing:border-box;font-size:14px;font-weight:900;margin-left:6px}
.sw a.on{background:#000;color:#fff}
.nap{left:4%;right:4%;top:21%;height:30%;border:3px dashed #000;}
.nap img{position:absolute;left:5%;top:50%;width:64px;height:64px;margin-top:-32px}
.nap .tx{position:absolute;left:22%;right:5%;top:50%;-webkit-transform:translateY(-50%);transform:translateY(-50%);
  font-size:19px;font-weight:800;line-height:1.3}
.nap .tx small{display:block;font-size:14px;color:#555;margin-top:4px}
.rk{position:absolute;left:4%;right:4%;height:7.4%}
.rk .n{position:absolute;left:0;top:50%;width:34px;height:34px;margin-top:-17px;border:3px solid #000;border-radius:17px;
  box-sizing:border-box;-webkit-box-sizing:border-box;text-align:center;font-size:16px;font-weight:900;line-height:28px}
.rk .n.top{background:#000;border-color:#000}
.rk .n img{width:22px;height:22px;margin-top:3px}
.rk .ic{position:absolute;left:44px;top:50%;width:30px;height:30px;margin-top:-15px}
.rk .nm{position:absolute;left:82px;width:34%;top:50%;margin-top:-20px;font-size:17px;font-weight:900;line-height:21px;
  white-space:nowrap;overflow:hidden}
.rk .rm{position:absolute;left:82px;width:34%;top:50%;margin-top:2px;font-size:13px;font-weight:700;color:#555;
  white-space:nowrap;overflow:hidden}
.rk .bar{position:absolute;left:52%;right:22%;top:50%;height:18px;margin-top:-9px;border:3px solid #000;border-radius:9px;
  box-sizing:border-box;-webkit-box-sizing:border-box;overflow:hidden}
.rk .bar span{position:absolute;left:0;top:0;bottom:0;background:#000}
.rk .t{position:absolute;right:0;width:21%;top:50%;margin-top:-20px;text-align:right;font-size:16px;font-weight:900;line-height:21px}
.rk .p{position:absolute;right:0;width:21%;top:50%;margin-top:2px;text-align:right;font-size:13px;font-weight:700;color:#555}
.none{left:6%;right:6%;top:62%;text-align:center;font-size:16px;font-weight:800;color:#555}
"""


def lights_page(h, d):
    on, u, week = d["on"], d["usage"], d["days"] > 1
    back = "/lights/week" if week else "/lights"
    out = header(h, d, "Lights", "lightbulb-group", (plural(len(on), "light") + " on") if on else "all off")
    out += f'<div class="abs sec" style="top:12.5%">{h.icon("lightbulb-on-outline")}On now'
    if on:
        out += form(h, "alloff", "all", back, f'{h.icon("lightbulb-group-off", "fff")}All off', "pill", "")
    out += "</div>"
    one_row = len(on) <= 2           # the ranking moves up and gets roomier
    rank_top, step = (37.5, 9.4) if one_row else (53, 7.6)
    if not on:
        out += (f'<div class="abs nap dash" style="height:14%">{corners(28)}{h.icon(h.pet["icon"], "000", "", big=True)}<div class="tx">All lights are off.'
                f'<small>{h.esc(d["cat"])} is napping in the dark (=-.-=) zzz</small></div></div>')
    else:
        shown = on[:4] if len(on) <= 4 else on[:3]
        rh = 14.5
        for i, dev in enumerate(shown):
            dev = dict(dev, dimmable=False, controls=[])   # an overview: tap to turn off, "..." for more
            out += device_card(h, dev, back, "sm", f' style="left:{4 + (i % 2) * 47}%;width:45%;'
                                                  f'top:{21 + (i // 2) * (rh + 1.5):.2f}%;height:{rh}%"')
        if len(on) > 4:
            out += (f'<a class="card info" href="/rooms" style="left:51%;width:45%;top:{21 + rh + 1.5}%;height:{rh}%">'
                    f'{corners()}<div class="vc" style="text-align:center;font-size:19px;font-weight:900">+ {len(on) - 3} more'
                    f'<br><small style="font-size:13px;font-weight:700">see Rooms</small></div></a>')
    total = f'<small>{h.esc(u["total"])} in all</small>' if u["rank"] else ""
    out += (f'<div class="abs sec" style="top:{rank_top}%">{h.icon("trophy-outline")}Most loved{total}<div class="sw">'
            f'<a href="/lights"{" class=\"on\"" if not week else ""}>24 h</a>'
            f'<a href="/lights/week"{" class=\"on\"" if week else ""}>7 days</a></div></div>')
    if not u["ok"]:
        out += '<div class="abs none">No history yet: Home Assistant\'s recorder keeps it. (=;.;=)</div>'
    elif not u["rank"]:
        out += f'<div class="abs none">No lights were on {"this week" if week else "in the last day"}. So dark! (=^.^=)</div>'
    top_pct = max(x["pct"] for x in u["rank"]) if u["rank"] else 1
    for i, x in enumerate(u["rank"]):
        badge = h.icon("crown", "fff", "") if i == 0 else str(i + 1)
        fill = max(4, round(100 * x["pct"] / max(top_pct, 1)))
        out += (f'<div class="rk" style="top:{rank_top + 8.5 + i * step:.1f}%"><span class="n{" top" if i == 0 else ""}">{badge}</span>'
                f'{h.icon(x["icon"], "000", "ic")}<span class="nm">{h.esc(x["name"])}</span>'
                f'<span class="rm">{h.esc(x["room"])}{" · on now" if x["on"] else ""}</span>'
                f'<span class="bar"><span style="width:{fill}%"></span></span>'
                f'<span class="t">{h.esc(x["time"])}</span><span class="p">{x["pct"]}% of the time</span></div>')
    return shell(h, "Lights", LIGHTS_CSS, out, "lights", d["refresh"], d["live"])


# --- Info (nothing about the house) -------------------------------------------------------------

INFO_CSS = """
.cal{left:4%;width:40%;top:13%;height:33%;border:3px solid #000;text-align:center}
.cal .m{position:absolute;left:0;right:0;top:0;height:25%;background:#000;color:#fff;font-size:20px;font-weight:900}
.cal>.k.ktl i,.cal>.k.ktr i{background:#000}.cal>.k{z-index:1}
.cal .m span{position:absolute;left:0;right:0;top:50%;margin-top:-13px;line-height:26px}
.cal .d{position:absolute;left:0;right:0;top:29%;font-size:82px;font-weight:900;line-height:1}
.cal .w{position:absolute;left:0;right:0;bottom:8%;font-size:18px;font-weight:900}
.yr{left:48%;right:4%;top:13%;height:15.5%;border:3px dashed #000;}
.yr .a{position:absolute;left:6%;right:4%;top:10%;font-size:19px;font-weight:900;white-space:nowrap}
.yr .hs{position:absolute;left:6%;right:4%;top:44%;height:20px;white-space:nowrap}
.yr .hs img{width:20px;height:20px;margin-right:3px}
.yr .b{position:absolute;left:6%;right:4%;bottom:9%;font-size:13px;font-weight:800;color:#444;white-space:nowrap}
.dl{left:48%;right:4%;top:30.5%;height:15.5%;background:#000;color:#fff;}
.dl img{position:absolute;left:5%;top:50%;width:40px;height:40px;margin-top:-20px}
.dl .a{position:absolute;left:28%;right:4%;top:50%;margin-top:-24px;font-size:22px;font-weight:900;line-height:26px;white-space:nowrap}
.dl .b{position:absolute;left:28%;right:4%;top:50%;margin-top:4px;font-size:13px;font-weight:700;line-height:15px}
.qt{left:4%;right:4%;top:48.5%;height:19.5%;border:3px dashed #000;}
.qt .q{position:absolute;left:4%;top:7%;width:34px;height:34px}
.qt .tx{position:absolute;left:14%;right:6%;top:50%;-webkit-transform:translateY(-50%);transform:translateY(-50%)}
.qt .tx p{margin:0;font-size:20px;font-weight:800;line-height:1.3}
.qt .tx p.s{font-size:17px}
.qt .tx b{display:block;text-align:right;font-size:15px;font-weight:900;margin-top:6px}
.ft{left:4%;right:4%;top:70%;height:16.5%;background:#000;color:#fff;}
.ft img{position:absolute;left:4%;top:50%;width:44px;height:44px;margin-top:-22px}
.ft .tx{position:absolute;left:17%;right:5%;top:50%;-webkit-transform:translateY(-50%);transform:translateY(-50%);
  font-size:17px;font-weight:800;line-height:1.3}
.ft .tx b{display:block;font-size:13px;font-weight:900;letter-spacing:1px}
.cd{position:absolute;top:89%;height:9%;border:3px solid #000;box-sizing:border-box;-webkit-box-sizing:border-box}
.cd img{position:absolute;left:9px;top:50%;width:28px;height:28px;margin-top:-14px}
.cd .a{position:absolute;left:44px;right:6px;top:50%;margin-top:-19px;font-size:14px;font-weight:900;line-height:18px;
  white-space:nowrap;overflow:hidden}
.cd .b{position:absolute;left:44px;right:6px;top:50%;margin-top:1px;font-size:13px;font-weight:700;color:#444;white-space:nowrap}
.cd.today{background:#000;color:#fff}.cd.today .b{color:#fff}
"""


def info_page(h, d):
    y, now = d["year"], d["now"]
    season = d["season"][0]
    out = header(h, d, "Info", "creation", season.lower() + " · week " + str(y["week"]))
    out += (f'<div class="abs cal">{corners(28)}<div class="m"><span>{h.esc(now.strftime("%B"))}</span></div>'
            f'<div class="d">{now.day}</div><div class="w">{h.esc(now.strftime("%A"))}</div></div>')
    filled = round(y["pct"] / 10)
    hs = "".join(h.icon("heart" if i < filled else "heart-outline", "000", "") for i in range(10))
    out += (f'<div class="abs yr dash">{corners(24)}<div class="a">Day {y["day"]} of {y["of"]}</div><div class="hs">{hs}</div>'
            f'<div class="b">{y["pct"]}% of {now.year} · {plural(y["left"], "day")} to go</div></div>')
    dl = d["daylight"]
    if dl:
        out += (f'<div class="abs dl nob dark">{corners(24)}{h.icon("weather-night" if d["sun"]["is_night"] else "white-balance-sunny", "fff", "")}'
                f'<div class="a">{h.esc(dl["length"])}</div><div class="b">of daylight today<br>{h.esc(dl["delta"])}</div></div>')
    else:
        out += (f'<div class="abs dl nob dark">{corners(24)}{h.icon(d["moon"]["icon"], "fff", "")}'
                f'<div class="a">{h.esc(d["moon"]["name"])}</div><div class="b">moon tonight</div></div>')
    q = d["quote"]
    out += (f'<div class="abs qt dash">{corners(28)}{h.icon("format-quote-open", "000", "q")}<div class="tx">'
            f'<p{" class=\"s\"" if len(q) > 80 else ""}>{h.esc(q)}</p><b>– {h.esc(d["quote_by"])}</b></div></div>')
    out += (f'<div class="abs ft nob dark">{corners(28)}{h.icon("lightbulb-on-outline", "fff", "")}<div class="tx"><b>DID YOU KNOW?</b>'
            f'{h.esc(d["fact"])}</div></div>')
    cds = d["countdowns"][:3]
    cw = 92 / max(len(cds), 1)
    for i, c in enumerate(cds):
        when = "today!" if c["days"] == 0 else "tomorrow" if c["days"] == 1 else f'in {c["days"]} days'
        today = c["days"] == 0
        out += (f'<div class="cd{" today on" if today else ""}" style="left:{4 + i * cw + 0.5:.2f}%;width:{cw - 1:.2f}%">{corners(22)}'
                f'{h.icon(c["icon"], "fff" if today else "000", "")}<span class="a">{h.esc(c["name"])}</span>'
                f'<span class="b">{when} · {h.esc(c["date"])}</span></div>')
    return shell(h, "Info", INFO_CSS, out, "info", d["refresh"], d["live"])


# --- One device ---------------------------------------------------------------------------------

DEVICE_CSS = """
.dh{left:4%;right:4%;top:13%;height:16%;border:3px dashed #000;}
.dh .ring{position:absolute;left:4%;top:50%;width:84px;height:84px;margin-top:-42px;border-radius:42px;border:3px solid #000;
  box-sizing:border-box;-webkit-box-sizing:border-box}
.dh .ring img{width:52px;height:52px;margin:13px 0 0 13px}
.dh .ring.on{background:#000}
.dh .a{position:absolute;left:27%;right:40%;top:50%;margin-top:-26px;font-size:24px;font-weight:900;line-height:28px;
  white-space:nowrap;overflow:hidden}
.dh .b{position:absolute;left:27%;right:40%;top:50%;margin-top:5px;font-size:15px;font-weight:700;color:#444;white-space:nowrap;overflow:hidden}
.dh .pw{position:absolute;right:4%;top:50%;margin-top:-27px;width:34%;height:54px}
.dh .pw form{position:absolute;top:0;bottom:0;width:48%;height:auto}
.dh .pw button{font-size:16px;font-weight:900}
.dl2{left:5%;right:5%;font-size:17px;font-weight:900;white-space:nowrap}
.dl2 img{width:22px;height:22px;vertical-align:-5px;margin-right:6px}
.dl2 small{font-size:13px;font-weight:700;color:#555;margin-left:6px}
.ch{position:absolute;height:7.4%}
.ch{border:3px solid #000;background:#fff;box-sizing:border-box;-webkit-box-sizing:border-box}
.ch button{font-size:15px;
  font-weight:900;white-space:nowrap;overflow:hidden;padding:0 6px}
.ch button img{width:22px;height:22px;vertical-align:-5px;margin-right:4px}
.ch.on{background:#000;color:#fff}
.ch.big button{font-size:30px;line-height:1}
.ch.big button img{width:34px;height:34px;margin:0}
.tv{position:absolute;height:7.4%;text-align:center;font-size:34px;font-weight:900;line-height:50px}
.tv small{font-size:14px;font-weight:800;color:#555;margin-left:6px}
.dstrip{left:4%;right:4%;bottom:1.5%;height:9%}
"""


def chip(h, action, eid, back, label, ic, on, style, value=None, big=False, color=None):
    col = color or ("fff" if on else "000")
    inner = (h.icon(ic, col, "") if ic else "") + (h.esc(label) if label else "")
    return form(h, action, eid, back, inner, "ch" + (" on" if on else "") + (" big" if big else ""), style, value=value, r=24)


def device_sections(h, d, back):
    """[(label html, rows: [[chip html builders(left, width, top)]])] for the device page."""
    dev, acts, cur, eid = d["dev"], d["acts"], d["current"], d["dev"]["eid"]
    secs = []

    def chips(items, per=4):
        return [items[i:i + per] for i in range(0, len(items), per)]

    if "level" in acts and h.cfg["level_style"] == "slider":
        pct = dev["pct"] or 0
        items = [lambda l, w, t: slider(h, dev, back, "000", "abs dslider",
                                       f' style="left:{l + 3}%;width:{w - 6}%;top:{t}%"')]
        secs.append((f'{h.icon("brightness-6")}Brightness<small>{f"{pct}%" if dev["on"] else "off"}</small>', chips(items, 1)))
    elif "level" in acts:
        pct = dev["pct"] or 0
        items = [(lambda l, w, t, lv=lv: chip(h, "level", eid, back, f"{lv}%",
                                             level_icon(h, dev["on"] and pct >= lv - 10),
                                             dev["on"] and abs(pct - lv) < 10,
                                             f' style="left:{l}%;width:{w}%;top:{t}%"', value=lv)) for lv in h.levels]
        secs.append((f'{h.icon("brightness-6")}Brightness<small>{f"{pct}%" if dev["on"] else "off"}</small>', chips(items, 5)))
    if d["buttons"]:
        items = [(lambda l, w, t, b=b: chip(h, "run", b["eid"], back, b["name"], b["icon"], False,
                                           f' style="left:{l}%;width:{w}%;top:{t}%"')) for b in d["buttons"]]
        secs.append((f'{h.icon("gesture-tap-button")}Buttons', chips(items, 2)))
    if "color" in acts:
        items = [(lambda l, w, t, c=c: chip(h, "color", eid, back, c[1], c[2], cur.get("color") == c[0],
                                           f' style="left:{l}%;width:{w}%;top:{t}%"', value=c[0])) for c in kinds.COLORS]
        secs.append((f'{h.icon("palette-outline")}Colour', chips(items)))
    if "white" in acts:
        items = [(lambda l, w, t, c=c: chip(h, "white", eid, back, c[1], c[2], cur.get("white") == c[0],
                                           f' style="left:{l}%;width:{w}%;top:{t}%"', value=c[0])) for c in kinds.WHITES]
        secs.append((f'{h.icon("white-balance-incandescent")}White', chips(items, 3)))
    if d.get("climate"):
        c = d["climate"]
        row = [(lambda l, w, t: chip(h, "cooler", eid, back, "", "minus", False, f' style="left:{l}%;width:{w}%;top:{t}%"', big=True)),
               (lambda l, w, t: f'<div class="tv" style="left:{l}%;width:{w}%;top:{t}%">{h.esc(c["target"])}°'
                                f'<small>target</small></div>'),
               (lambda l, w, t: chip(h, "warmer", eid, back, "", "plus", False, f' style="left:{l}%;width:{w}%;top:{t}%"', big=True))]
        secs.append((f'{h.icon("thermometer")}Temperature<small>{h.esc(c["now"])}° inside now</small>', [row]))
    for key, title, ic, words in (("mode", "Mode", "tune-variant", kinds.HVAC_WORDS), ("fanmode", "Fan", "fan", None),
                                  ("effect", "Effects", "creation", None), ("source", "Source", "remote-tv", None),
                                  ("option", "Choose", "format-list-bulleted", None)):
        opts = d["opts"].get(key)
        if not opts:
            continue
        items = [(lambda l, w, t, o=o, key=key, words=words: chip(h, key, eid, back, kinds.word(o, words),
                                           (words or {}).get(o, (None, None))[1], cur.get(key) == o,
                                           f' style="left:{l}%;width:{w}%;top:{t}%"', value=o)) for o in opts]
        secs.append((f'{h.icon(ic)}{title}', chips(items)))
    if dev["domain"] == "media_player" and dev["controls"]:
        vol = d.get("volume")
        items = [(lambda l, w, t, a=a, ic=ic: chip(h, a, eid, back, "", ic, False, f' style="left:{l}%;width:{w}%;top:{t}%"', big=True))
                 for a, ic in (("voldown", "volume-minus"), ("playpause", "play-pause"), ("volup", "volume-plus"))]
        secs.append((f'{h.icon("volume-high")}Sound{f"<small>volume {vol}%</small>" if vol is not None else ""}', [items]))
    if dev["domain"] == "cover":
        items = [(lambda l, w, t, a=a, ic=ic, nm=nm: chip(h, a, eid, back, nm, ic, False, f' style="left:{l}%;width:{w}%;top:{t}%"'))
                 for a, ic, nm in (("open", "arrow-up", "Open"), ("stop", "stop", "Stop"), ("close", "arrow-down", "Close"))]
        secs.append((f'{h.icon(dev["icon"])}Move', [items]))
    return secs


def pack(secs, top, bottom):
    """Split sections over pages so each page fits between top and bottom (% of the page)."""
    pages, y = [[]], top
    for title, rows in secs:
        need = 6 + 8.6 * len(rows)
        if y + need > bottom and pages[-1]:
            pages.append([])
            y = top
        pages[-1].append((title, rows))
        y += need
    return pages


def device_page(h, d, back_to, page_no=1):
    dev = d["dev"]
    eid = dev["eid"]
    here = f'/device/{h.quote(eid)}?b={h.quote(back_to)}'
    out = header(h, d, dev["name"], dev["icon"], d["room"], back=back_to)
    ring = "on" if dev["on"] else ""
    sub = dev["state"]
    out += (f'<div class="abs dh dash">{corners(28)}<div class="ring {ring}">{h.icon(dev["icon"], "fff" if dev["on"] else "000", "", big=True)}</div>'
            f'<div class="a">{h.esc(dev["name"])}</div><div class="b">{h.esc(sub)}</div>')
    if "on" in d["acts"]:
        out += ('<div class="pw">' + chip(h, "on", eid, here, "On", "power", dev["on"], ' style="left:0"') +
                chip(h, "off", eid, here, "Off", "power", not dev["on"],
                     ' style="right:0"') + '</div>')
    elif dev["main"]:
        out += '<div class="pw">' + chip(h, dev["main"], eid, here, "Go", "play", False, ' style="right:0"') + '</div>'
    out += "</div>"
    y = 31.5
    secs = device_sections(h, d, here + f"&p={page_no}")
    pages = pack(secs, y, 99)
    if len(pages) > 1:
        pages = pack(secs, y, 88)   # room for the pager
    page_no = min(max(page_no, 1), len(pages))
    for title, rows in pages[page_no - 1]:
        out += f'<div class="abs dl2" style="top:{y}%">{title}</div>'
        y += 5
        for row in rows:
            w = 92 / max(len(r) for r in rows)   # a short last row keeps the chip width of the others
            for i, make in enumerate(row):
                out += make(4 + i * w + 0.6, round(w - 1.2, 2), y)
            y += 8.6
        y += 1
    if len(pages) > 1:
        out += '<div class="abs dstrip">' + pager(h, page_no, len(pages), here) + '</div>'
    if not secs:
        out += f'<div class="abs empty">{h.esc(dev["name"])} only turns on and off. (=^.^=)</div>'
    return shell(h, dev["name"], HOME_CSS + DEVICE_CSS, out, "rooms", d["refresh"], d["live"])


# --- Settings -----------------------------------------------------------------------------------

SETTINGS_CSS = """
.lbl{left:5%;right:5%;font-size:17px;font-weight:900}
.lbl img{width:22px;height:22px;vertical-align:-5px;margin-right:6px}
.lbl small{font-size:13px;font-weight:700;color:#555;margin-left:6px}
.sty{position:absolute;height:13.5%}
.sty{border:3px solid #000;background:#fff;box-sizing:border-box;-webkit-box-sizing:border-box}
.sty.on{background:#000;color:#fff}
.sty img.i{display:block;width:36px;height:36px;margin:0 auto}
.sty span{display:block;font-size:15px;font-weight:900;margin-top:2px}
.sty img.h{position:absolute;right:10px;top:9px;width:18px;height:18px}
.rf{position:absolute;height:7%}
.rf{border:3px solid #000;background:#fff;box-sizing:border-box;-webkit-box-sizing:border-box}
.rf button{font-size:15px;font-weight:900}
.rf.on{background:#000;color:#fff}
.rf.rm button{white-space:nowrap;overflow:hidden;padding:0 6px;font-size:14px}
.rf.rm img{width:20px;height:20px;vertical-align:-5px;margin-right:4px}
.cfg{left:4%;right:4%;top:81%;height:17%;border:3px dashed #000;}
.cfg .cat{position:absolute;left:4%;top:50%;width:60px;height:60px;margin-top:-30px}
.cfg .tx{position:absolute;left:23%;right:4%;top:50%;-webkit-transform:translateY(-50%);transform:translateY(-50%);
  font-size:15px;font-weight:800;line-height:1.3}
.cfg b{display:block;font-size:19px;font-weight:900;margin-top:4px}
.bed{position:absolute;right:4%;top:2.2%;width:36%;height:54px;background:#000;color:#fff}
.bed button{font-size:17px;font-weight:900;white-space:nowrap}
.bed img{width:24px;height:24px;vertical-align:-6px;margin-right:6px}
"""


def settings_page(h, d, url):
    """Kindle settings: home style, where the kiosk hangs, update intervals. The rest is on /config."""
    out = header(h, {"time": "", "weather": None}, "Settings", "cog-outline", "make it yours")
    y = 13
    out += (f'<div class="abs lbl" style="top:{y}%">{h.icon("palette-outline")}Home style'
            f'<small>tap one, then Home</small></div>')
    for i, (n, name, ic) in enumerate(STYLES):
        on = d["home_style"] == n
        col = "fff" if on else "000"
        heart = h.icon("heart", "fff", "h") if on else ""
        out += setting(h, "home_style", n, "/settings", f'{heart}{h.icon(ic, col, "i")}<span>{name}</span>',
                       "sty" + (" on" if on else ""), f' style="left:{4 + i * 18.6:.1f}%;width:17.4%;top:{y + 4.5}%;height:11%"',
                       r=24)
    y += 18.5
    here = d["kiosk_area"] or d["home_area"]
    rooms = d["rooms"][:8]
    if rooms:
        out += (f'<div class="abs lbl" style="top:{y}%">{h.icon("map-marker-outline")}Move kiosk'
                f'<small>where it hangs now</small></div>')
        per = 4
        for i, r in enumerate(rooms):
            on = r["id"] == here
            col = "fff" if on else "000"
            main = h.icon("heart", col) if r["id"] == d["home_area"] else h.icon(r["icon"], col)
            out += setting(h, "kiosk_area", "" if r["id"] == d["home_area"] else r["id"], "/settings",
                           f'{main}{h.esc(r["name"])}', "rf rm" + (" on" if on else ""),
                           f' style="left:{4 + (i % per) * 23.25}%;width:21.5%;top:{y + 4.5 + (i // per) * 8}%"', r=22)
        y += 4.5 + 8 * math.ceil(len(rooms) / per) + 2
    out += (f'<div class="abs lbl" style="top:{y}%">{h.icon("lightning-bolt-outline")}Live updates'
            f'<small>check for changes, reload only then</small></div>')
    for i, (sec, name) in enumerate(LIVE_LABELS):
        on = d["live_seconds"] == sec
        out += setting(h, "live_seconds", sec, "/settings", name, "rf" + (" on" if on else ""),
                       f' style="left:{4 + i * 18.6}%;width:17%;top:{y + 4.5}%"', r=22)
    y += 14
    out += (f'<div class="abs lbl" style="top:{y}%">{h.icon("refresh")}Full refresh'
            f'<small>clears e-ink ghosting, flashes once</small></div>')
    for i, (sec, name) in enumerate(REFRESH_LABELS):
        on = d["refresh_seconds"] == sec
        out += setting(h, "refresh_seconds", sec, "/settings", name, "rf" + (" on" if on else ""),
                       f' style="left:{4 + i * 23.25}%;width:21.5%;top:{y + 4.5}%"', r=22)
    y += 14
    out += (f'<div class="abs cfg dash" style="top:{y}%;bottom:1.5%;height:auto">{corners(26)}{h.icon(h.pet["icon"], "000", "cat")}<div class="tx">'
            f'Devices, names, icons, rooms and more: open this on your computer'
            f'<b>{h.esc(url.replace("http://", ""))}/config</b></div></div>'
            + setting(h, "sleep", "bed", "/", f'{h.icon("sleep", "fff")}Going to bed', "bed nob dark", r=26))
    return shell(h, "Settings", SETTINGS_CSS, out, "settings", 0, d["live_seconds"])


# --- Downtime -----------------------------------------------------------------------------------

SLEEP_CSS = """
#page{bottom:0}
.sky{left:0;right:0;top:0;bottom:0}
.sky .st{position:absolute}
.moonbox{left:50%;top:13%;width:250px;height:250px;margin-left:-125px;border-radius:125px;background:#000}
.moonbox .pet{position:absolute;left:50%;top:50%;width:150px;height:150px;margin:-68px 0 0 -75px}
.moonbox .z{position:absolute;right:14px;top:18px;width:50px;height:50px}
.dream{left:6%;right:6%;top:53%;text-align:center}
.dream .t{font-size:30px;font-weight:900;line-height:1.2}
.dream .s{font-size:18px;font-weight:800;color:#444;margin-top:10px}
.dream .w{font-size:15px;font-weight:700;color:#666;margin-top:14px}
.wake{position:absolute;left:24%;width:52%;top:80%;height:64px;background:#000;color:#fff}
.wake button{font-size:22px;font-weight:900}
.wake img{width:30px;height:30px;vertical-align:-7px;margin-right:8px}
"""
SLEEP_STARS = [(8, 6, 22, "star-four-points"), (84, 9, 30, "star"), (16, 30, 18, "star-outline"),
               (78, 34, 22, "star-four-points-outline"), (7, 39, 26, "weather-night"), (90, 43, 18, "star"),
               (12, 70, 20, "star-four-points"), (86, 72, 24, "cloud-outline"), (30, 4, 16, "star"),
               (64, 3, 20, "star-four-points-outline"), (48, 94, 18, "star-outline"), (10, 92, 22, "star")]


def sleep_page(h, d):
    """Downtime: the pet asleep in the moon, a Wake up button. Checks in every 2 minutes, no clock, no flashes."""
    you = f", {h.esc(d['you'])}" if d.get("you") else ""
    stars = "".join(f'<span class="st" style="left:{x}%;top:{y}%;width:{sz}px;height:{sz}px">{h.icon(ic, "000", "")}</span>'
                    for x, y, sz, ic in SLEEP_STARS)
    out = (f'<div class="abs sky">{stars}</div>'
           f'<div class="abs moonbox">{h.icon(h.pet["icon"], "fff", "pet", big=True)}{h.icon("sleep", "fff", "z")}</div>'
           f'<div class="abs dream"><div class="t">Shhh... {h.esc(d["cat"])} is fast asleep</div>'
           f'<div class="s">Sweet dreams{you}! (=-.-=) zzz</div>'
           f'<div class="w">Resting until {h.esc(d["wake"])} to save battery</div></div>'
           + setting(h, "sleep", "wake", "/", f'{h.icon("white-balance-sunny", "fff")}Wake up', "wake nob dark", r=30))
    return shell(h, "Sleeping", SLEEP_CSS, out, "", 0, 120, idle=0, tabs=False)


# --- Error --------------------------------------------------------------------------------------

def error_page(h, exc):
    out = (f'<div class="abs hello" style="top:20%;height:40%"><div class="vc" style="text-align:center">'
           f'{h.icon("cat", "000", "")}<p style="font-size:22px;font-weight:900;margin:8px 0">'
           f'Oh no! I can\'t reach Home Assistant</p><p style="font-size:14px;font-weight:700;color:#555;margin:0 20px">'
           f'{h.esc(exc)}</p><p style="font-size:15px;font-weight:800">Trying again in a minute... (=;.;=)</p></div></div>')
    css = HOME_CSS + ".hello img{width:90px;height:90px}"
    return shell(h, "Oops", css, out, "home", 60, 0)


def message_page(h, title, text, link=None):
    """A plain message on the kiosk (not set up, not paired). No tabs: nothing here works without access."""
    a = (f'<p style="font-size:16px;font-weight:900;margin:14px 0 0"><a href="{h.esc(link[0])}" style="color:#000;'
         f'border-bottom:2px solid #000">{h.esc(link[1])}</a></p>') if link else ""
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{h.esc(title)}</title>'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="refresh" content="120"><style>{FONT_CSS}body{{margin:0;background:#fff;color:#000;'
            f'font-family:"Kiosk Nunito",Nunito,sans-serif;text-align:center}}.m{{padding:18% 8% 0}}'
            f'.m img{{width:90px;height:90px}}</style>{KINDLE_ZOOM}</head><body><div class="m">{h.icon("cat", "000", "")}'
            f'<p style="font-size:24px;font-weight:900;margin:8px 0">{h.esc(title)}</p>'
            f'<p style="font-size:16px;font-weight:700;color:#444;margin:0">{h.esc(text)}</p>{a}</div></body></html>')
