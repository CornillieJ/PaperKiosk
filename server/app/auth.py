"""Who may use PaperKiosk.

Two secrets, both created by ./install.sh (scripts/10-configure.sh) in ./secrets and mounted read-only:

- kiosk_key: a random key. The screen opens the kiosk once with ?key=<kiosk_key> (the installer puts that URL in
  the Kindle app); the server answers with a long-lived cookie (pk_kiosk) and the screen uses the kiosk from then
  on. Without it, no page, no button, nothing from Home Assistant.
- admin_password: a PBKDF2 hash of the password for /config (the settings page). Logging in gives an admin
  cookie (pk_admin, 30 days) that also opens the kiosk pages (the live preview).

Cookies are HttpOnly and SameSite=Strict, so another website open in the same browser can't use them (no
cross-site requests, no JSONP reads of /x.js). On top of that, POSTs and button presses must come from this
site (Origin / Referer / Sec-Fetch-Site), and the /config form carries a CSRF token.
"""
import hashlib
import hmac
import os
import secrets
import threading
import time
from pathlib import Path

SECRETS = Path(os.environ.get("SECRETS_DIR", "/run/secrets"))
KIOSK_COOKIE, ADMIN_COOKIE = "pk_kiosk", "pk_admin"
ADMIN_DAYS = 30
KIOSK_YEARS = 10
ITERATIONS = 310_000


def _read(name):
    try:
        return (SECRETS / name).read_text().strip()
    except OSError:
        return ""


def kiosk_key():
    """The kiosk key ("" when the installer hasn't made one yet: then nothing but /health works). Read every
    time (a tiny file): a new key or password from the installer works without a restart."""
    return _read("kiosk_key")


def _mac(*parts):
    secret = hashlib.sha256(b"paperkiosk-session:" + kiosk_key().encode()).digest()
    return hmac.new(secret, ".".join(parts).encode(), hashlib.sha256).hexdigest()


# --- Password --------------------------------------------------------------------------------

def hash_password(password, iterations=ITERATIONS):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def admin_configured():
    return _read("admin_password").startswith("pbkdf2_sha256$")


def check_password(password):
    stored = _read("admin_password")
    try:
        algo, iterations, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        got = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, digest)


_fails = {}   # ip -> [count, first failure time]
_fails_lock = threading.Lock()


def login_blocked(ip):
    """After 10 wrong passwords in 15 minutes, an IP has to wait out the rest of those 15 minutes."""
    with _fails_lock:
        n, t0 = _fails.get(ip, (0, 0))
        if time.time() - t0 > 900:
            _fails.pop(ip, None)
            return False
        return n >= 10


def login_failed(ip):
    with _fails_lock:
        n, t0 = _fails.get(ip, (0, time.time()))
        if len(_fails) > 1000:
            _fails.clear()
        _fails[ip] = (n + 1, t0)
    time.sleep(1)   # slows guessing down


def login_ok(ip):
    with _fails_lock:
        _fails.pop(ip, None)


# --- Cookies ---------------------------------------------------------------------------------

def cookies(header):
    out = {}
    for part in (header or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k:
            out[k] = v
    return out


def _cookie(name, value, max_age):
    return f"{name}={value}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Strict"


def kiosk_token():
    return _mac("kiosk")


def kiosk_cookie():
    return _cookie(KIOSK_COOKIE, kiosk_token(), KIOSK_YEARS * 365 * 86400)


def key_ok(key):
    k = kiosk_key()
    return bool(k) and hmac.compare_digest((key or "").encode(), k.encode())


def admin_cookie():
    exp = str(int(time.time()) + ADMIN_DAYS * 86400)
    return _cookie(ADMIN_COOKIE, f"{exp}.{_mac('admin', exp)}", ADMIN_DAYS * 86400)


def logout_cookie():
    return _cookie(ADMIN_COOKIE, "", 0)


def is_admin(jar):
    if not kiosk_key():
        return False
    exp, _, mac = jar.get(ADMIN_COOKIE, "").partition(".")
    return exp.isdigit() and int(exp) > time.time() and hmac.compare_digest(mac, _mac("admin", exp))


def is_kiosk(jar):
    return bool(kiosk_key()) and hmac.compare_digest(jar.get(KIOSK_COOKIE, ""), kiosk_token())


def csrf_token(jar):
    """For forms on /config: tied to the admin cookie, so another site can't know it."""
    return _mac("csrf", jar.get(ADMIN_COOKIE, ""))


def csrf_ok(jar, token):
    return hmac.compare_digest(csrf_token(jar), token or "")


# --- Same-site checks ------------------------------------------------------------------------

def same_site(headers):
    """False when the browser says the request comes from another site. Old browsers (the Kindle's WebKit)
    send none of these headers for their own pages: then the cookie's checks are what counts."""
    host = headers.get("Host", "")
    fetch_site = headers.get("Sec-Fetch-Site")
    if fetch_site and fetch_site not in ("same-origin", "none"):
        return False
    origin = headers.get("Origin")
    if origin is not None:
        return origin.split("://", 1)[-1] == host
    referer = headers.get("Referer")
    if referer:
        return referer.split("://", 1)[-1].split("/", 1)[0] == host
    return True


if __name__ == "__main__":   # python auth.py hash  (password on stdin) -> the line for secrets/admin_password
    import sys
    if sys.argv[1:] == ["hash"]:
        pw = sys.stdin.readline().rstrip("\n")
        if len(pw) < 8:
            sys.exit("password too short (8 characters or more)")
        print(hash_password(pw))
    else:
        sys.exit("usage: python auth.py hash < password")
