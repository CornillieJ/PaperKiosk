"""Checks the connection to Home Assistant, for the installer (scripts/20-home-assistant.sh).

  python check_ha.py probe <url> [<url> ...]   -> the first URL where Home Assistant answers (exit 1: none)
  python check_ha.py check [--shell]            -> HA_URL + the token in /run/secrets/ha_token: one JSON line

check prints {"ok": true, "version", "location", "user", "admin", "areas", "entities"} or {"ok": false, "error"};
with --shell the same as shell assignments (HA_OK=1, HA_AREA_IDS=(...), ...), safely quoted for eval.
"""
import json
import shlex
import sys
import urllib.error
import urllib.request


def probe(urls):
    for url in urls:
        url = url.rstrip("/")
        try:
            urllib.request.urlopen(url + "/api/", timeout=3)
        except urllib.error.HTTPError as e:
            if e.code == 401:   # Home Assistant's API, asking for a token
                print(url)
                return 0
        except Exception:
            pass
    return 1


def emit(d, shell):
    if not shell:
        print(json.dumps(d))
        return
    for k, v in d.items():
        name = "HA_" + k.upper()
        if isinstance(v, list):
            print(f"{name}=(" + " ".join(shlex.quote(str(x)) for x in v) + ")")
        else:
            print(f"{name}=" + shlex.quote("1" if v is True else "" if v in (False, None) else str(v)))


def check(shell=False):
    import server   # reads HA_URL and the token like the kiosk does
    try:
        user, conf, areas, states = server.ha({"type": "auth/current_user"}, {"type": "get_config"},
                                               {"type": "config/area_registry/list"}, {"type": "get_states"})
    except Exception as exc:
        msg = str(exc) or type(exc).__name__
        if "refused the token" in msg:
            msg = "Home Assistant refused the token (copied completely? still valid?)"
        emit({"ok": False, "error": msg, "url": server.HA_URL}, shell)
        return 1
    emit({"ok": True, "url": server.HA_URL, "version": conf.get("version"),
                      "location": conf.get("location_name"), "user": user.get("name"),
                      "admin": bool(user.get("is_admin")), "areas": [a["name"] for a in areas],
                      "area_ids": [a["area_id"] for a in areas], "entities": len(states)}, shell)
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["probe"]:
        sys.exit(probe(sys.argv[2:]))
    if sys.argv[1:2] == ["check"]:
        sys.exit(check("--shell" in sys.argv))
    sys.exit(__doc__)
