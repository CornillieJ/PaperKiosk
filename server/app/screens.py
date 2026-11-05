"""Screens with their own settings ("kiosks" in config.json), for scripts/add-screen.sh.

  python screens.py list                                   -> one line per screen: id<TAB>name<TAB>ip
  python screens.py add <name> <ip> [<room id>]            -> adds (or updates the screen with that IP);
                                                              prints its id. Room: its own main room (and Home shows
                                                              that room's devices until cards are picked for it).
  python screens.py areas                                  -> shell assignments PK_AREA_IDS=(...) PK_AREAS=(...)
Values come in as arguments (never pasted into code) and go through config.clean().
"""
import shlex
import sys

import config


def add(name, ip, room=""):
    data = config.get()
    if not config.IP_RE.match(ip or ""):
        sys.exit(f"not an IP address: {ip}")
    if room and not config.AREA_RE.match(room):
        sys.exit(f"not a room id: {room}")
    kiosks = [dict(k) for k in data["kiosks"]]
    same = next((k for k in kiosks if k["ip"] == ip), None)
    if same:   # this screen is known already: rename it, keep its settings
        same["name"] = name.strip()[:30] or same["name"]
        kid = same["id"]
    else:
        if len(kiosks) >= 10:
            sys.exit("10 screens with their own settings already (the maximum)")
        kid, n = config.slug(name), 2
        while any(k["id"] == kid for k in kiosks):
            kid, n = f"{config.slug(name)[:27]}-{n}", n + 1
        kiosks.append({"id": kid, "name": name.strip()[:30] or kid, "ip": ip, "settings": {}})
    if room:
        k = next(k for k in kiosks if k["id"] == kid)
        # its own room: also its own Home cards (none picked = that room's lights and switches, automatically)
        k["settings"] = {**k["settings"], "home_area": room, "kiosk_area": "", "home_devices": [], "home_scenes": []}
    saved = config.save({**data, "kiosks": kiosks})
    if not any(k["id"] == kid for k in saved["kiosks"]):
        sys.exit("could not save the screen")
    print(kid)


def areas():
    import server
    from check_ha import one_line
    rooms = server.ha({"type": "config/area_registry/list"})[0]
    print("PK_AREA_IDS=(" + " ".join(shlex.quote(one_line(a["area_id"])) for a in rooms) + ")")
    print("PK_AREAS=(" + " ".join(shlex.quote(one_line(a["name"])) for a in rooms) + ")")


if __name__ == "__main__":
    cmd, args = (sys.argv[1:2] or [""])[0], sys.argv[2:]
    if cmd == "list":
        for k in config.get()["kiosks"]:
            print(f'{k["id"]}\t{k["name"]}\t{k["ip"]}')
    elif cmd == "add" and len(args) in (2, 3):
        add(*args)
    elif cmd == "areas":
        areas()
    else:
        sys.exit(__doc__)
