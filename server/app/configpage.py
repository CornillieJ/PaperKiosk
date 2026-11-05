"""The /config page: edit config.json from a PC browser (desktop layout, scrolls, live Kindle preview).

With more than one kiosk the page edits one at a time (?kiosk=<id>): settings marked "this screen" are saved
for that kiosk only (config.KIOSK_KEYS), the rest is shared. The preview shows the kiosk being edited
(the hk_as cookie). Cards can be dragged around in the preview of Home: that saves the new order.

render() draws the form from the current config and everything HA has (hidden things included);
parse() turns the submitted form back into a config dict. Entities/areas that were not on the form
(e.g. temporarily missing from HA) keep their saved settings. Entities HA added since the last save
are listed first under "New in Home Assistant" and stay off the Kindle until "Show" is ticked.
"""
import config
import kinds
import pets

STYLE_NAMES = [(5, "Kawaii"), (1, "Cozy"), (2, "Bubbles"), (3, "Sky"), (4, "Paper")]
LEVEL_ICON_NAMES = [("heart", "Hearts", "heart"), ("star", "Stars", "star"), ("paw", "Paws", "paw"),
                    ("flower", "Flowers", "flower"), ("circle", "Dots", "checkbox-blank-circle"),
                    ("lightbulb", "Bulbs", "lightbulb"), ("drop", "Drops", "water")]
HELLO_NAMES = [("auto", "Automatic"), ("large", "Large"), ("medium", "Medium"),
               ("small", "Small"), ("off", "Hidden")]
PART_NAMES = [("weather", "Weather"), ("bins", "Bin day"), ("indoor", "Inside temperature"),
              ("moon", "Moon & sunrise line")]
TAB_NAMES = [("rooms", "Rooms"), ("lights", "Lights"), ("weather", "Weather"), ("info", "Info"), ("settings", "Settings")]
HOURS = [(hr, f"{hr:02d}:00") for hr in range(24)]
IDLE_NAMES = [(60, "after 1 minute"), (120, "after 2 minutes"), (300, "after 5 minutes"), (600, "after 10 minutes"),
              (1800, "after 30 minutes"), (0, "Never")]
LIVE_NAMES = [(3, "every 3 seconds"), (5, "every 5 seconds"), (10, "every 10 seconds"), (30, "every 30 seconds"),
              (0, "Off")]
REFRESH_NAMES = [(300, "every 5 minutes"), (600, "every 10 minutes"), (1800, "every 30 minutes"), (0, "Off")]
HOME_DOMAINS = ("light", "switch", "fan", "input_boolean", "cover", "lock", "climate", "media_player", "humidifier",
                "vacuum", "select", "input_select")
INFO = ("sensor", "binary_sensor")
SLOTS = 6
SCENE_DOMAINS = ("scene", "script", "button", "input_button")

CSS = """
@font-face{font-family:"Nunito";src:url(/font/nunito-400.woff) format("woff");font-weight:400}
@font-face{font-family:"Nunito";src:url(/font/nunito-700.woff) format("woff");font-weight:700}
@font-face{font-family:"Nunito";src:url(/font/nunito-900.woff) format("woff");font-weight:900}
*{box-sizing:border-box}
body{margin:0;font-family:Nunito,system-ui,sans-serif;background:#f6f6f6;color:#111;font-size:15px}
.wrap{max-width:1560px;margin:0 auto;padding:24px;display:grid;grid-template-columns:minmax(0,1fr) 470px;gap:28px}
@media(max-width:1100px){.wrap{grid-template-columns:minmax(0,1fr)}.side{position:static!important}}
h1{font-size:30px;font-weight:900;margin:0 0 4px}
h1 img{width:40px;height:40px;vertical-align:-8px;margin-right:8px}
.lead{color:#555;font-weight:700;margin:0 0 14px}
.box{background:#fff;border:3px solid #000;border-radius:24px;padding:18px 22px;margin-bottom:20px;min-width:0}
.box h2{font-size:20px;font-weight:900;margin:0 0 4px}
.box h2 img{width:26px;height:26px;vertical-align:-6px;margin-right:6px}
.box h3{font-size:16px;font-weight:900;margin:16px 0 6px}
.box p.hint{margin:0 0 14px;color:#555;font-weight:700;font-size:14px}
label.f{display:block;font-weight:900;margin:10px 0 4px}
input[type=text],select,textarea{font:inherit;font-weight:700;padding:8px 12px;border:2px solid #000;border-radius:14px;
  background:#fff;width:100%;min-width:0;max-width:100%;text-overflow:ellipsis}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:4px 24px}
.slots{display:flex;flex-wrap:wrap;gap:10px 18px}
.slot{display:flex;gap:10px;align-items:center;width:calc(50% - 9px);min-width:240px}
.slot>.sn{flex:0 0 72px;font-weight:800}.slot>select{flex:1 1 auto;width:auto;min-width:0}
/* device and room rows: a grid that never overflows; two lines when the column is narrow */
.rows{border-top:1px dashed #bbb}
.erow{display:grid;gap:6px 10px;align-items:center;padding:8px 2px;border-bottom:1px dashed #bbb;
  grid-template-columns:30px minmax(0,1.5fr) minmax(0,1fr) minmax(0,1fr) minmax(0,.8fr) minmax(0,1fr) 48px;
  grid-template-areas:"ic nm kd nk ico bt sh"}
.erow.head{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#555;font-weight:900;padding:4px 2px}
.erow>.ic{grid-area:ic}.erow>.nm{grid-area:nm;min-width:0}.erow>.kd{grid-area:kd}.erow>.nk{grid-area:nk}
.erow>.ico{grid-area:ico}.erow>.bt{grid-area:bt}.erow>.sh{grid-area:sh;text-align:center}
.erow .nm b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.erow .risky{display:block;font-size:12px;font-weight:900;color:#a00;margin-top:2px}
.erow small{display:block;color:#777;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.erow img{width:26px;height:26px}
.erow input[type=text],.erow select{padding:6px 10px;font-size:14px;border-radius:12px}
.erow .fl>span{display:none;font-size:11px;font-weight:900;text-transform:uppercase;color:#555;margin:0 0 2px 4px}
@media(max-width:1640px){
  .erow{grid-template-columns:30px repeat(3,minmax(0,1fr)) 48px;grid-template-areas:"ic nm nm kd sh" ". nk ico bt ."}
  .erow.head{display:none}.erow .fl>span{display:block}}
.rrow{display:grid;gap:10px;align-items:center;padding:8px 2px;border-bottom:1px dashed #bbb;
  grid-template-columns:30px minmax(0,1fr) 80px minmax(0,1fr) 48px}
.rrow.head{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#555;font-weight:900;padding:4px 2px}
.rrow img{width:26px;height:26px}.rrow small{display:block;color:#777;font-weight:700}
.rrow input[type=text]{padding:6px 10px;font-size:14px;border-radius:12px}
.pick{position:relative}
.pick>summary{list-style:none;border:2px solid #000;border-radius:12px;padding:6px 10px;font-size:14px;font-weight:700;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer;background:#fff}
.pick>summary::-webkit-details-marker{display:none}
.pick[open]>div{position:absolute;z-index:5;left:0;top:100%;margin-top:4px;background:#fff;border:2px solid #000;
  border-radius:12px;padding:8px 10px;min-width:220px;max-height:260px;overflow:auto;box-shadow:0 6px 18px rgba(0,0,0,.15)}
.pick label{display:block;font-weight:700;font-size:14px;padding:3px 0;white-space:nowrap}
details.room{border:2px solid #000;border-radius:18px;padding:8px 14px;margin:10px 0;background:#fff}
details.room>summary{font-weight:900;cursor:pointer;font-size:16px}
summary img{width:22px;height:22px;vertical-align:-5px;margin-right:6px}
.save{position:sticky;bottom:16px;text-align:right;pointer-events:none}
.save button{pointer-events:auto;font:inherit;font-weight:900;font-size:18px;background:#000;color:#fff;border:0;border-radius:24px;
  padding:14px 30px;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.2)}
.ok{background:#000;color:#fff;border-radius:18px;padding:10px 18px;font-weight:900;margin-bottom:18px}
.side{position:sticky;top:20px;align-self:start}
.frame{width:470px;height:630px;border:10px solid #222;border-radius:28px;overflow:hidden;background:#fff}
.frame iframe{width:597px;height:800px;border:0;transform:scale(.7538);transform-origin:0 0}
.tabs a{display:inline-block;margin:8px 6px 0 0;padding:6px 12px;border:2px solid #000;border-radius:14px;
  font-weight:900;color:#000;text-decoration:none;background:#fff}
.small{font-size:13px;color:#555;font-weight:700}
textarea{max-width:520px}
.box.new{border-style:dashed;background:#fffbea}
ol.steps{margin:6px 0 0;padding-left:22px;font-weight:700;line-height:1.6}
ol.steps b{font-weight:900}
a{color:#000}
h1 a.logout{float:right;font-size:14px;font-weight:900;border:2px solid #000;border-radius:14px;padding:6px 12px;
  text-decoration:none;margin-top:6px}
/* picture choices (pet, brightness) */
.tiles{display:flex;flex-wrap:wrap;gap:8px}
.tile{position:relative;display:block;cursor:pointer}
.tile input{position:absolute;opacity:0;pointer-events:none}
.tile span{display:block;min-width:84px;text-align:center;border:2px solid #000;border-radius:16px;padding:8px 10px 6px;
  font-weight:900;font-size:13px;background:#fff}
.tile span img{display:block;width:34px;height:34px;margin:0 auto 2px}
.tile input:checked+span{background:#000;color:#fff}
.tile input:checked+span img{filter:invert(1)}
.tile input:checked+span .mini{color:#fff}
.tile input:focus-visible+span{outline:3px solid #f0a}
.tile span.mini{border:0;background:none;padding:0;min-width:0;border-radius:0}
.mini{display:flex;gap:3px;justify-content:center;height:34px;align-items:center}
.mini img{width:16px!important;height:16px!important;margin:0!important;display:inline-block!important}
.mini.sl i{display:block;width:70px;height:10px;border:2px solid currentColor;border-radius:6px;position:relative}
.mini.sl i:before{content:"";position:absolute;left:0;top:0;bottom:0;width:60%;background:currentColor}
.mini.sl i:after{content:"";position:absolute;left:60%;top:50%;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:7px;
  background:currentColor}
.checks{display:flex;flex-wrap:wrap;gap:6px 18px}.checks label{font-weight:800}
.kbar{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px;align-items:center}
.kbar a{display:inline-block;padding:7px 14px;border:2px solid #000;border-radius:16px;font-weight:900;text-decoration:none;
  background:#fff}
.kbar a.on{background:#000;color:#fff}
.kb{display:inline-block;font-size:11px;font-weight:900;border:1.5px solid #000;border-radius:8px;padding:0 6px;margin-left:6px;
  vertical-align:2px;color:#000;background:#fff}
.kb.own{background:#000;color:#fff}
.editing{border:3px dashed #000;border-radius:18px;padding:10px 16px;margin-bottom:16px;font-weight:800;background:#fff}
.nav{display:flex;flex-wrap:wrap;gap:6px 14px;margin:0 0 16px;font-weight:900}
.nav a{text-decoration:none;border-bottom:2px solid #000}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#000;color:#fff;font-weight:900;
  padding:10px 20px;border-radius:18px;opacity:0;transition:opacity .3s;pointer-events:none}
.toast.show{opacity:1}
.krow{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(0,1.2fr) 90px;gap:10px;align-items:center;
  padding:8px 0;border-bottom:1px dashed #bbb}
.krow.head{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#555;font-weight:900}
.btnline{display:flex;gap:10px;align-items:center;margin:6px 0}
button.lite{font:inherit;font-weight:900;border:2px solid #000;background:#fff;border-radius:14px;padding:6px 14px;cursor:pointer}
"""

def _sel(name, options, current, blank=None):
    out = f'<select name="{name}">'
    if blank is not None:
        out += f'<option value="">{blank}</option>'
    for group, opts in options:
        if group:
            out += f'<optgroup label="{group}">'
        for value, text in opts:
            sel = " selected" if str(value) == str(current) else ""
            out += f'<option value="{value}"{sel}>{text}</option>'
        if group:
            out += "</optgroup>"
    return out + "</select>"


def kind_select(esc, eid, current):
    opts = [("", "Automatic")] + [(k, v[0]) for k, v in kinds.KINDS.items()]
    return _sel(f"kind:{esc(eid)}", [(None, opts)], current)


def countdown_text(cfg):
    return "\n".join(f'{c["name"]} = {c["date"][3:]}/{c["date"][:2]}' for c in cfg["countdowns"])


def tiles(name, options, current, kind="radio"):
    """Picture choices: [(value, label, inner html)]."""
    cur = current if isinstance(current, list) else [current]
    return '<div class="tiles">' + "".join(
        f'<label class="tile"><input type="{kind}" name="{name}" value="{v}"{" checked" if v in cur else ""}>'
        f'<span>{inner}{label}</span></label>' for v, label, inner in options) + "</div>"


DRAG_JS = """
(function(){
var form=document.getElementById('cfg'),pv=document.getElementById('pv'),toast=document.getElementById('toast');
document.cookie='hk_as='+(form.dataset.kiosk||'-')+';path=/;max-age=31536000;samesite=lax';
pv.src='/';
function say(t){toast.textContent=t;toast.classList.add('show');setTimeout(function(){toast.classList.remove('show')},1800)}
// The Kindle draws rounded boxes from corner pieces (fast on e-ink); in this scaled preview they leave hairlines.
function corners(doc){doc.querySelectorAll('b.k').forEach(function(k){var m=k.className.match(/\\bk(\\d+)\\b/),p=k.parentElement;
  if(m&&p&&!p.dataset.r){p.style.borderRadius=m[1]+'px';p.dataset.r='1'}k.style.display='none'})}
var drag=null,justDragged=false;
function cards(doc){return Array.prototype.slice.call(doc.querySelectorAll('.card[data-eid]'))}
function bind(doc){if(doc.location.pathname!=='/')return;cards(doc).forEach(function(c){if(c.dataset.dnd)return;
  c.dataset.dnd='1';c.style.cursor='grab';c.addEventListener('mousedown',function(e){if(e.button!==0)return;
  e.preventDefault();drag={c:c,doc:doc,x:e.clientX,y:e.clientY,moved:false}})})}
function setup(){var doc;try{doc=pv.contentDocument}catch(e){return}if(!doc||!doc.body)return;
  corners(doc);bind(doc);
  new MutationObserver(function(){corners(doc);bind(doc)}).observe(doc.body,{childList:true,subtree:true});
  doc.addEventListener('mousemove',function(e){if(!drag)return;var dx=e.clientX-drag.x,dy=e.clientY-drag.y;
    if(!drag.moved&&Math.abs(dx)+Math.abs(dy)<8)return;drag.moved=true;var s=drag.c.style;
    s.transform='translate('+dx+'px,'+dy+'px) scale(.96)';s.zIndex=50;s.opacity=.85;s.cursor='grabbing';
    cards(doc).forEach(function(c){c.style.outline=''});var t=over(doc,e,drag.c);if(t&&t!==drag.c)t.style.outline='4px dashed #888'});
  doc.addEventListener('mouseup',function(e){if(!drag)return;var d=drag;drag=null;if(!d.moved)return;
    justDragged=true;setTimeout(function(){justDragged=false},300);
    var t=over(doc,e,d.c),s=d.c.style;s.transform=s.zIndex=s.opacity='';cards(doc).forEach(function(c){c.style.outline=''});
    if(!t||t===d.c)return;var order=cards(doc).map(function(c){return c.dataset.eid}),
      a=order.indexOf(d.c.dataset.eid),b=order.indexOf(t.dataset.eid);order[a]=t.dataset.eid;order[b]=d.c.dataset.eid;
    save(order)});
  doc.defaultView.addEventListener('click',function(e){if(justDragged){e.preventDefault();e.stopPropagation()}},true)}
function over(doc,e,c){c.style.visibility='hidden';var el=doc.elementFromPoint(e.clientX,e.clientY);
  c.style.visibility='';return el&&el.closest('.card[data-eid]')}
function save(order){var sel=form.querySelectorAll('select[name=home_device]');
  for(var i=0;i<sel.length;i++)sel[i].value=order[i]||'';
  var fd=new URLSearchParams(new FormData(form));fd.append('ajax','1');
  fetch('/config',{method:'POST',body:fd}).then(function(r){if(!r.ok)throw r;say('New order saved \\u2665');
    pv.contentWindow.location.reload()}).catch(function(){say('Could not save, try the Save button')})}
pv.addEventListener('load',setup);
document.getElementById('openall').addEventListener('click',function(){var d=document.querySelectorAll('details.room'),
  open=!d[0]||!d[0].open;d.forEach(function(x){x.open=open});this.textContent=open?'Close all rooms':'Open all rooms'});
})();
"""


def render(h, base, data, saved=False, editing="", open_all=False):
    """The page; editing: id of the kiosk whose own settings are edited ("" = main settings)."""
    esc = h.esc
    cfg = config.effective(base, editing) if editing else base
    kiosk = next((k for k in base["kiosks"] if k["id"] == editing), None)
    rooms = data["rooms"]
    areas = [(r["id"], r["name"]) for r in rooms if r["id"] != "_other"]
    every = [e for r in rooms for e in r["entities"]]

    def kb(key):
        """A small "this screen" badge on settings a kiosk can have for itself (black: differs from main)."""
        if not kiosk or key not in config.KIOSK_KEYS:
            return ""
        own = key in kiosk["settings"]
        return f'<span class="kb{" own" if own else ""}" title="{"Own setting of" if own else "Can differ on"} {esc(kiosk["name"])}">this screen</span>'

    def entity_options(domains, test=None):
        groups = []
        for r in rooms:
            opts = [(e["eid"], esc(f'{e["nick"] or e["friendly"] or e["eid"]}')) for e in r["entities"]
                    if e["domain"] in domains and (test is None or test(e))]
            if opts:
                groups.append((esc(r["name"]), opts))
        return groups

    def check(name, key, text):
        return (f'<label class="f"><input type="checkbox" name="{name}" value="1"{" checked" if cfg[key] else ""}> '
                f'{text}{kb(key)}</label>')

    temp_opts = entity_options(("sensor",), lambda e: e["dc"] == "temperature")
    hum_opts = entity_options(("sensor",), lambda e: e["dc"] == "humidity")
    pet = pets.get(cfg["mascot"])
    general = (
        '<div class="grid2">'
        f'<div><label class="f">{esc(pet["name"])}\'s name{kb("cat_name")}</label><input type="text" name="cat_name" maxlength="20" value="{esc(cfg["cat_name"])}"></div>'
        f'<div><label class="f">Your name <span class="small">(for greetings, optional)</span></label>'
        f'<input type="text" name="your_name" maxlength="20" value="{esc(cfg["your_name"])}"></div>'
        f'<div><label class="f">Main room <span class="small">(where the kiosk lives)</span>{kb("home_area")}</label>'
        f'{_sel("home_area", [(None, [(a, esc(n)) for a, n in areas])], cfg["home_area"], "Automatic: the first room")}</div>'
        f'<div><label class="f">Kiosk is in <span class="small">(moved for a while?)</span>{kb("kiosk_area")}</label>'
        f'{_sel("kiosk_area", [(None, [(a, esc(n)) for a, n in areas if a != cfg["home_area"]])], cfg["kiosk_area"], "The main room")}</div>'
        f'<div><label class="f">Weather{kb("weather_entity")}</label>{_sel("weather_entity", [(None, [(w, esc(w)) for w in data["weathers"]])], cfg["weather_entity"], "First weather in Home Assistant")}</div>'
        f'<div><label class="f">Inside temperature <span class="small">(on Home)</span>{kb("indoor_temp")}</label>'
        f'{_sel("indoor_temp", temp_opts, cfg["indoor_temp"], "Automatic: first one in the kiosk room")}</div>'
        f'<div><label class="f">Inside humidity{kb("indoor_humidity")}</label>'
        f'{_sel("indoor_humidity", hum_opts, cfg["indoor_humidity"], "Automatic: first one in the kiosk room")}</div>'
        f'<div><label class="f">Live updates{kb("live_seconds")}</label>{_sel("live_seconds", [(None, LIVE_NAMES)], cfg["live_seconds"])}'
        '<div class="small">The Kindle asks for changes this often and redraws only what changed.</div></div>'
        f'<div><label class="f">Full refresh{kb("refresh_seconds")}</label>{_sel("refresh_seconds", [(None, REFRESH_NAMES)], cfg["refresh_seconds"])}'
        '<div class="small">Reload anyway, clears e-ink ghosting (the screen flashes once).</div></div>'
        '</div>'
        + check("show_unavailable", "show_unavailable", 'Show devices that are unavailable (drawn dashed, "napping")')
        + check("approve_new", "approve_new", 'New devices in Home Assistant wait here until I tick "Show"')
        + check("seasonal", "seasonal", "Seasonal decorations (snow in December, pumpkins at Halloween)"))

    pet_tiles = tiles("mascot", [(k, v[0], h.icon(v[1])) for k, v in pets.PETS.items()], cfg["mascot"])
    style_tiles = tiles("level_style", [
        ("icons", "Icons (5 steps)", '<span class="mini">' + h.icon(kinds_level(cfg, True)) * 3
         + h.icon(kinds_level(cfg, False)) * 2 + "</span>"),
        ("slider", "Slider (10 steps)", '<span class="mini sl"><i></i></span>')], cfg["level_style"])
    icon_tiles = tiles("level_icon", [(k, n, h.icon(ic)) for k, n, ic in LEVEL_ICON_NAMES], cfg["level_icon"])
    look = (
        f'<label class="f">Pet{kb("mascot")}</label>{pet_tiles}'
        '<div class="grid2">'
        f'<div><label class="f">Home style{kb("home_style")}</label>{_sel("home_style", [(None, STYLE_NAMES)], cfg["home_style"])}</div>'
        f'<div><label class="f">Pet\'s box on Home{kb("hello_size")}</label>{_sel("hello_size", [(None, HELLO_NAMES)], cfg["hello_size"])}'
        '<div class="small">Automatic: smaller when there are more cards.</div></div>'
        f'<div><label class="f">Clock{kb("clock_24h")}</label>{_sel("clock_24h", [(None, [("1", "24 hours (21:30)"), ("0", "12 hours (9:30)")])], "1" if cfg["clock_24h"] else "0")}</div>'
        f'<div><label class="f">Back to Home when nobody taps{kb("idle_home")}</label>{_sel("idle_home", [(None, IDLE_NAMES)], cfg["idle_home"])}</div>'
        f'<div><label class="f">Downtime from{kb("sleep_from")}</label>{_sel("sleep_from", [(None, HOURS)], cfg["sleep_from"])}</div>'
        f'<div><label class="f">Downtime until{kb("sleep_to")}</label>{_sel("sleep_to", [(None, HOURS)], cfg["sleep_to"])}'
        '<div class="small">A sleepy screen that checks in every 2 minutes and never flashes: saves battery. The same hour '
        'twice = no downtime. "Going to bed" on the Kindle\'s Settings starts it early.</div></div>'
        '</div>'
        f'<label class="f">Brightness on the cards{kb("level_style")}</label>{style_tiles}'
        f'<label class="f">Brightness icons{kb("level_icon")}</label>{icon_tiles}'
        f'<label class="f">Home also shows{kb("home_parts")}</label><div class="checks">'
        + "".join(f'<label><input type="checkbox" name="home_parts" value="{k}"{" checked" if k in cfg["home_parts"] else ""}> {n}</label>'
                  for k, n in PART_NAMES) + '</div>'
        f'<label class="f">Tabs next to Home{kb("tabs")}</label><div class="checks">'
        + "".join(f'<label><input type="checkbox" name="tabs" value="{k}"{" checked" if k in cfg["tabs"] else ""}> {n}</label>'
                  for k, n in TAB_NAMES) + '</div>'
        '<div class="small">Without the Settings tab, the kiosk can only be set up from here.</div>')

    dev_opts = entity_options(HOME_DOMAINS)
    slots = '<div class="slots">' + "".join(
        f'<div class="slot"><span class="sn">Card {i + 1}</span>{_sel("home_device", dev_opts, (cfg["home_devices"] + [""] * SLOTS)[i], "— empty —")}</div>'
        for i in range(SLOTS)) + "</div>"
    scene_opts = entity_options(SCENE_DOMAINS)
    scene_slots = ('<div class="slots">' + "".join(
        f'<div class="slot"><span class="sn">Button {i + 1}</span>{_sel("home_scene", scene_opts, (cfg["home_scenes"] + [""] * 3)[i], "— none —")}</div>'
        for i in range(3)) + "</div>") if scene_opts else '<p class="small">No scenes or scripts in Home Assistant yet.</p>'
    buttons = [(e["eid"], e["nick"] or e["friendly"] or e["eid"]) for e in every if e["domain"] in SCENE_DOMAINS]

    def button_pick(e):
        if e["domain"] in INFO + SCENE_DOMAINS or not buttons:
            return ""
        picked = [n for b, n in buttons if b in e["buttons"]]
        label = ", ".join(picked) if picked else "none"
        opts = "".join(f'<label><input type="checkbox" name="buttons:{esc(e["eid"])}" value="{esc(b)}"'
                       f'{" checked" if b in e["buttons"] else ""}> {esc(n)}</label>' for b, n in buttons)
        return f'<details class="pick"><summary>{esc(label)}</summary><div>{opts}</div></details>'

    def fl(label, inner):
        return f'<label class="fl"><span>{label}</span>{inner}</label>' if inner else ""

    def entity_row(e, new=False):
        eid = e["eid"]
        if new:
            vis = f'<input type="checkbox" name="show_new" value="{esc(eid)}" title="Show">'
        else:
            vis = f'<input type="checkbox" name="hide" value="{esc(eid)}" title="Hide"{" checked" if eid in cfg["hidden"] else ""}>'
        room = f' · {esc(e["room"])}' if new else ""
        risky = ""
        if e.get("risky"):
            what = "unlock" if e["domain"] == "lock" else "open"
            risky = (f'<label class="risky" title="Anyone at the screen can then {what} it"><input type="checkbox" '
                     f'name="allow_risky" value="{esc(eid)}"{" checked" if e["allow_risky"] else ""}> '
                     f'&#9888; allow {what} from the kiosk</label>')
        return (f'<div class="erow"><div class="ic">{h.icon(e["kind_icon"])}</div>'
                f'<div class="nm"><b title="{esc(e["friendly"] or eid)}">{esc(e["friendly"] or eid)}</b><small title="{esc(eid)}">{esc(eid)}{room}</small>'
                f'{risky}<input type="hidden" name="seen" value="{esc(eid)}"></div>'
                f'<div class="kd">{fl("Kind", kind_select(esc, eid, e["kind_cfg"]) if e["domain"] not in INFO else "")}</div>'
                f'<div class="nk">{fl("Nickname", f"""<input type="text" name="nick:{esc(eid)}" value="{esc(e["nick"])}" maxlength="30" placeholder="{esc(e["name"])}">""")}</div>'
                f'<div class="ico">{fl("Icon", f"""<input type="text" name="icon:{esc(eid)}" value="{esc(e["icon_cfg"])}" placeholder="{esc(e["kind_icon"])}">""")}</div>'
                f'<div class="bt">{fl("Buttons on its page", button_pick(e))}</div><div class="sh">{fl("Show" if new else "Hide", vis)}</div></div>')

    def head(last):
        return (f'<div class="erow head"><div></div><div>Device</div><div>Kind</div><div>Nickname</div><div>Icon</div>'
                f'<div>{"Buttons on its page" if buttons else ""}</div><div>{last}</div></div>')

    for r in rooms:
        for e in r["entities"]:
            e["room"] = r["name"]
    new_ents = [e for e in every if e["new"]]
    new_box = ""
    if new_ents:
        new_box = (f'<div class="box new" id="new"><h2>{h.icon("gift-outline")}New in Home Assistant ({len(new_ents)})</h2>'
                   '<p class="hint">These are not on the Kindle yet. Give them a kind and a cute name, tick <b>Show</b> '
                   '(the box on the right) and save. Not ready yet (an IR blaster still being set up)? Leave it empty: '
                   'they wait here.</p><div class="rows">' + head("Show")
                   + "".join(entity_row(e, True) for e in new_ents) + '</div></div>')

    room_rows = ""
    for r in rooms:
        if r["id"] == "_other":
            continue
        rid = r["id"]
        hidden = rid in cfg["hidden_areas"]
        order = cfg["area_order"].index(rid) + 1 if rid in cfg["area_order"] else ""
        room_rows += (f'<div class="rrow"><div>{h.icon(r["icon"])}</div><div><b>{esc(r["name"])}</b><small>{esc(rid)}</small>'
                      f'<input type="hidden" name="seen_area" value="{esc(rid)}"></div>'
                      f'<div><input type="text" name="order:{esc(rid)}" value="{order}" placeholder="–"></div>'
                      f'<div><input type="text" name="icon:area:{esc(rid)}" value="{esc(cfg["icons"].get("area:" + rid, ""))}" placeholder="{esc(r["icon"])}"></div>'
                      f'<div style="text-align:center"><input type="checkbox" name="hide_area" value="{esc(rid)}"{" checked" if hidden else ""}></div></div>')

    ent_html = ""
    for r in rooms:
        ents = [e for e in r["entities"] if not e["new"]]
        if not ents:
            continue
        ent_html += (f'<details class="room"{" open" if open_all else ""}><summary>{h.icon(r["icon"])}{esc(r["name"])} '
                     f'<span class="small">({len(ents)})</span></summary><div class="rows">' + head("Hide")
                     + "".join(entity_row(e) for e in ents) + '</div></details>')

    seen_ips = {k["ip"] for k in base["kiosks"]}
    ip_opts = "".join(f'<option value="{esc(ip)}">{"Kindle" if "Kindle" in ua or "armv7" in ua else "browser"}, seen '
                      f'{_ago(t)}</option>' for ip, t, ua in data.get("clients", []) if ip not in seen_ips)
    kiosk_rows = "".join(
        f'<div class="krow"><input type="text" name="kname:{esc(k["id"])}" value="{esc(k["name"])}" maxlength="30">'
        f'<input type="text" name="kip:{esc(k["id"])}" value="{esc(k["ip"])}" maxlength="45">'
        f'<div class="small">{len(k["settings"])} own setting{"s" if len(k["settings"]) != 1 else ""} · '
        f'<a href="/config?kiosk={esc(k["id"])}">edit</a></div>'
        f'<label class="small"><input type="checkbox" name="kdel" value="{esc(k["id"])}"> remove</label></div>'
        for k in base["kiosks"])
    kiosks_box = (
        f'<div class="box" id="kiosks"><h2>{h.icon("tablet")}Screens</h2>'
        '<p class="hint">One Kindle? Nothing to do here: it uses the main settings. Another screen (a second Kindle, an '
        'old tablet) can get its own room, Home cards, pet, tabs, ... Add it with its IP address (fixed in the router), '
        'then pick it at the top of this page. Screens that are not listed use the main settings.</p>'
        + (('<div class="krow head"><div>Name</div><div>IP address</div><div></div><div></div></div>' + kiosk_rows) if kiosk_rows else "")
        + '<h3>Add a screen</h3><div class="krow"><input type="text" name="new_kname" maxlength="30" placeholder="e.g. Bedroom Kindle">'
        f'<input type="text" name="new_kip" maxlength="45" list="ips" placeholder="192.168.1.…"><datalist id="ips">{ip_opts}</datalist>'
        '<div class="small">Recently seen screens are suggested in the IP box.</div><div></div></div></div>')

    kbar = ""
    if base["kiosks"]:
        kbar = ('<div class="kbar"><span class="small">Editing:</span>'
                f'<a href="/config"{" class=on" if not kiosk else ""}>Main settings</a>'
                + "".join(f'<a href="/config?kiosk={esc(k["id"])}"{" class=on" if kiosk and k["id"] == kiosk["id"] else ""}>'
                          f'{esc(k["name"])}</a>' for k in base["kiosks"]) + "</div>")
    if kiosk:
        kbar += (f'<div class="editing">Editing <b>{esc(kiosk["name"])}</b> ({esc(kiosk["ip"])}). Settings marked '
                 '<span class="kb">this screen</span> are saved for this screen only (black: different from the main '
                 'settings; set it back to the same value to follow the main settings again). Everything else is shared.</div>')

    kinds_list = ", ".join(v[0] for v in kinds.KINDS.values())
    howto = f"""<details class="box"{" open" if new_ents else ""}><summary>{h.icon("star-four-points")}How to add a new device, the cute way</summary>
<ol class="steps">
<li>In <b>Home Assistant</b>: add the device and give it an <b>area</b> (Settings &gt; Devices &gt; the device &gt; Area).
That's the room it shows up in here.</li>
<li>Reload this page: it appears under <b>New in Home Assistant</b> at the top (not on the Kindle yet).</li>
<li>Pick a <b>Kind</b>: it chooses the icon and the extras. ({esc(kinds_list)}.)
Lamps, strips and Christmas lights count as lights: they're on the Lights tab and in the "most loved" ranking.
Christmas lights also add twinkly decorations on Home when they're on.</li>
<li>Give it a <b>Nickname</b> (e.g. "Christmas lights"), or an <b>Icon</b> of your own from
<a href="https://pictogrammers.com/library/mdi/" target="_blank">Material Design Icons</a>.</li>
<li>Extra buttons? IR remotes are often scripts or buttons in HA (LED colours, TV input, ...). Pick them under
<b>Buttons on its page</b>: they show on the device's own page (the round "..." on its card).</li>
<li>Tick <b>Show</b> and <b>Save</b>. Want it on Home? Choose it as one of the Home screen cards below.</li>
<li>Check the preview on the right (tap the card's "..."), and you're done. (=^.^=)</li>
</ol>
<p class="small">Locks, garage doors and gates: the kiosk can lock and close them, but only unlocks or opens
the ones you tick <b>allow unlock/open</b> for (anyone standing at the screen could use it).</p>
<p class="small">Colours, brightness, AC modes and fan speeds, TV sources and effect lists come from Home Assistant
automatically: if HA can do it, the device page shows it.</p></details>"""

    ok = f'<div class="ok">Saved! The Kindle shows it in a few seconds. {esc(pet["faces"][0])} ♥</div>' if saved else ""
    nav = ('<div class="nav">' + "".join(f'<a href="#{a}">{t}</a>' for a, t in (
        ("general", "General"), ("look", "Look"), ("home", "Home screen"), ("countdowns", "Countdowns"),
        ("rooms", "Rooms"), ("devices", "Devices"), ("kiosks", "Screens"))) + "</div>")
    body = f"""
<div class="wrap"><div>
<h1>{h.icon(pet["icon"])}PaperKiosk settings <a class="logout" href="/logout">Log out</a></h1>
<p class="lead">Everything here is saved to <code>data/config.json</code> (you can edit that file too).</p>
{kbar}{nav}{ok}
<form method="post" action="/config" id="cfg" data-kiosk="{esc(editing)}">
<input type="hidden" name="kiosk" value="{esc(editing)}"><input type="hidden" name="csrf" value="{esc(data.get("csrf", ""))}">
{new_box}
{howto}
<div class="box" id="general"><h2>{h.icon("heart-outline")}General</h2>{general}</div>
<div class="box" id="look"><h2>{h.icon("palette-outline")}Look &amp; layout</h2>
<p class="hint">How the kiosk looks. The preview on the right shows it after saving.</p>{look}</div>
<div class="box" id="home"><h2>{h.icon("home-heart")}Home screen cards</h2>
<p class="hint">Up to {SLOTS} cards on Home{kb("home_devices")}, in this order (1-2 big cards, 3-4 in a grid, 5-6 a
little smaller; an odd last card fills its row). Leave all empty to show the lights and switches of the room
automatically. <b>Or drag the cards around in the preview</b>: that saves the new order at once.</p>{slots}
<h3>Buttons at the bottom{kb("home_scenes")}</h3>
<p class="hint">Up to 3 scenes or scripts (e.g. "Movie night").</p>{scene_slots}</div>
<div class="box" id="countdowns"><h2>{h.icon("calendar-heart")}Countdowns</h2>
<p class="hint">Birthdays and other nice days for the Info tab, one per line as <code>Name = day/month</code>
(e.g. <code>{esc(cfg["cat_name"])}'s birthday = 20/11</code>). Christmas, New Year, Easter, ... are already there.</p>
<textarea name="countdowns" rows="4">{esc(countdown_text(cfg))}</textarea></div>
<div class="box" id="rooms"><h2>{h.icon("home-group")}Rooms</h2>
<p class="hint">Order: rooms with a number come first (1, 2, ...), the rest follow in Home Assistant's order.
Icon: any <a href="https://pictogrammers.com/library/mdi/" target="_blank">Material Design Icon</a> name, like
<code>sofa</code>, <code>bed</code>, <code>stove</code>. Hidden rooms disappear from the Rooms tab.</p>
<div class="rows"><div class="rrow head"><div></div><div>Room</div><div>Order</div><div>Icon</div><div>Hide</div></div>{room_rows}</div></div>
<div class="box" id="devices"><h2>{h.icon("lamp")}Devices</h2>
<p class="hint">Kind, cute nickname, a different icon, extra buttons, or hide them everywhere. Empty = Home Assistant's
name and a matching icon.</p><div class="btnline"><button type="button" class="lite" id="openall">Open all rooms</button></div>{ent_html}</div>
{kiosks_box}
<div class="save"><button>Save ♥</button></div>
</form></div>
<div class="side"><div class="frame"><iframe id="pv" name="pv" src="about:blank"></iframe></div>
<div class="tabs"><a href="/" target="pv">Home</a><a href="/rooms" target="pv">Rooms</a><a href="/lights" target="pv">Lights</a>
<a href="/weather" target="pv">Weather</a><a href="/info" target="pv">Info</a><a href="/settings" target="pv">Settings</a></div>
<p class="small">Live preview of {esc(kiosk["name"]) if kiosk else "the Kindle screen"} (taps here really switch things!).
Drag cards on Home to reorder them.<br>Kindle URL: {esc(data["url"])}</p></div></div>
<div class="toast" id="toast"></div>"""
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>PaperKiosk settings</title>'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style></head>'
            f'<body>{body}<script>{DRAG_JS}</script></body></html>')


def kinds_level(cfg, full):
    names = dict((k, ic) for k, _, ic in LEVEL_ICON_NAMES)
    ic = names.get(cfg["level_icon"], "heart")
    outline = {"checkbox-blank-circle": "checkbox-blank-circle-outline", "water": "water-outline"}
    return ic if full else outline.get(ic, ic + "-outline")


def _ago(t):
    import time
    m = int((time.time() - t) // 60)
    return "just now" if m < 1 else f"{m} min ago" if m < 60 else f"{m // 60} h ago"


def parse_countdowns(text):
    out = []
    for line in (text or "").splitlines():
        name, _, when = line.partition("=")
        parts = when.strip().replace("-", "/").replace(".", "/").split("/")
        if name.strip() and len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            out.append({"name": name.strip()[:30], "date": f"{int(parts[1]):02d}-{int(parts[0]):02d}"})
    return out


def parse(fields, base):
    """Form fields (name -> [values]) to (new config, id of the kiosk edited). Settings of things not on the form
    are kept; when a kiosk is edited, its KIOSK_KEYS go into its own settings, the rest into the shared ones."""
    one = lambda k: (fields.get(k) or [""])[0]
    editing = one("kiosk")
    editing = editing if any(k["id"] == editing for k in base["kiosks"]) else ""
    cfg = config.effective(base, editing) if editing else base
    new = dict(cfg)
    new.update(cat_name=one("cat_name"), your_name=one("your_name"), home_area=one("home_area") or cfg["home_area"],
               kiosk_area=one("kiosk_area"), show_unavailable=one("show_unavailable") == "1",
               approve_new=one("approve_new") == "1", seasonal=one("seasonal") == "1",
               weather_entity=one("weather_entity"), indoor_temp=one("indoor_temp"),
               indoor_humidity=one("indoor_humidity"), countdowns=parse_countdowns(one("countdowns")),
               mascot=one("mascot") or cfg["mascot"], level_style=one("level_style") or cfg["level_style"],
               level_icon=one("level_icon") or cfg["level_icon"], clock_24h=one("clock_24h") != "0",
               hello_size=one("hello_size") or cfg["hello_size"], home_parts=fields.get("home_parts", []),
               tabs=fields.get("tabs", []))
    for key in ("home_style", "refresh_seconds", "live_seconds", "idle_home", "sleep_from", "sleep_to"):
        if one(key).isdigit():
            new[key] = int(one(key))
    devs, scenes = [], []
    for e in fields.get("home_device", []):
        if e and e not in devs:
            devs.append(e)
    for e in fields.get("home_scene", []):
        if e and e not in scenes:
            scenes.append(e)
    new["home_devices"], new["home_scenes"] = devs, scenes

    seen = set(fields.get("seen", []))
    nick, icons, kind, btns = dict(cfg["nicknames"]), dict(cfg["icons"]), dict(cfg["kinds"]), dict(cfg["buttons"])
    for eid in seen:
        for store, prefix in ((nick, "nick:"), (icons, "icon:"), (kind, "kind:")):
            v = one(prefix + eid).strip()
            if v:
                store[eid] = v
            else:
                store.pop(eid, None)
        picked = [b for b in fields.get("buttons:" + eid, []) if b]
        chosen = [b for b in btns.get(eid, []) if b in picked] + [b for b in picked if b not in btns.get(eid, [])]
        if chosen:
            btns[eid] = chosen
        else:
            btns.pop(eid, None)
    new["kinds"], new["buttons"] = kind, btns
    shown_new = set(fields.get("show_new", []))
    known = set(cfg["known"] or [])
    pending = {e for e in seen if e not in known and cfg["known"] is not None and cfg["approve_new"]}
    waiting = pending - shown_new   # not shown yet: they stay under "New in Home Assistant"
    new["hidden"] = sorted((set(cfg["hidden"]) - seen) | set(fields.get("hide", [])))
    new["allow_risky"] = sorted((set(cfg["allow_risky"]) - seen) | (set(fields.get("allow_risky", [])) & seen))
    new["known"] = sorted(known | (seen - waiting))

    seen_areas = fields.get("seen_area", [])
    for rid in seen_areas:
        v = one("icon:area:" + rid).strip()
        if v:
            icons["area:" + rid] = v
        else:
            icons.pop("area:" + rid, None)
    new["nicknames"], new["icons"] = nick, icons
    new["hidden_areas"] = sorted((set(cfg["hidden_areas"]) - set(seen_areas)) | set(fields.get("hide_area", [])))
    numbered = []
    for rid in seen_areas:
        v = one("order:" + rid).strip()
        if v.isdigit():
            numbered.append((int(v), rid))
    new["area_order"] = [rid for _, rid in sorted(numbered)]

    # screens
    removed = set(fields.get("kdel", []))
    kiosks = []
    for k in base["kiosks"]:
        if k["id"] in removed:
            continue
        kiosks.append({**k, "name": one("kname:" + k["id"]).strip() or k["name"],
                       "ip": one("kip:" + k["id"]).strip() or k["ip"]})
    name, ip = one("new_kname").strip(), one("new_kip").strip()
    if name and ip:
        kid, n = config.slug(name), 2
        while any(k["id"] == kid for k in kiosks):
            kid, n = f"{config.slug(name)[:27]}-{n}", n + 1
        kiosks.append({"id": kid, "name": name[:30], "ip": ip, "settings": {}})
    new.pop("kiosk", None)
    new.pop("kiosk_name", None)
    if editing:
        shared = {k: v for k, v in new.items() if k not in config.KIOSK_KEYS}
        out = config.clean({**base, **shared, "kiosks": kiosks})
        for k in out["kiosks"]:
            if k["id"] == editing:
                k["settings"] = config.own_settings(out, new)
        return config.clean(out), (editing if editing not in removed else "")
    new["kiosks"] = kiosks
    return config.clean(new), ""


def login_page(h, error="", ready=True):
    """The password page for /config."""
    esc = h.esc
    if ready:
        inner = ('<form method="post" action="/login"><label class="f" for="pw">Password</label>'
                 '<input type="password" id="pw" name="password" autocomplete="current-password" autofocus required>'
                 '<div style="margin-top:16px"><button class="go">Log in</button></div></form>'
                 '<p class="small">Forgot it? On the server: <code>./install.sh</code> &gt; Configure &gt; new password.</p>')
    else:
        inner = '<p class="lead">Not set up yet: run <code>./install.sh</code> on the server first.</p>'
    err = f'<div class="err">{esc(error)}</div>' if error else ""
    css = CSS + (".login{max-width:420px;margin:12vh auto;padding:0 20px}.err{background:#a00;color:#fff;border-radius:14px;"
                 "padding:8px 14px;font-weight:900;margin-bottom:12px}input[type=password]{font:inherit;font-weight:700;"
                 "padding:8px 12px;border:2px solid #000;border-radius:14px;width:100%}button.go{font:inherit;font-weight:900;"
                 "font-size:17px;background:#000;color:#fff;border:0;border-radius:20px;padding:10px 26px;cursor:pointer}")
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>PaperKiosk: log in</title>'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head><body>'
            f'<div class="login"><div class="box"><h1>{h.icon("cat")}PaperKiosk</h1>{err}{inner}</div></div></body></html>')
