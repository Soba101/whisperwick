"""Access rules for the play page: the shared key, the allowed Host names and the cookies.

The page may be shared over a public HTTPS name. So a key is required then, and the key is
checked in constant time, so its length-matching prefix cannot be guessed from timing.
"""

import hmac
from http.cookies import SimpleCookie

KEY_COOKIE = "ww_key"
GAME_COOKIE = "ww_game"
LOCAL_NAMES = ("127.0.0.1", "localhost")


def allowed_hosts(port: int, names: tuple[str, ...] = ()) -> set[str]:
    """Host header values we accept: our own address, plus each allowed name (any usual form)."""
    hosts = {f"{n}:{port}" for n in LOCAL_NAMES}
    for name in names:
        name = name.lower()
        hosts |= {name, f"{name}:443", f"{name}:{port}"}
    return hosts


def is_local(host: str | None) -> bool:
    """True for the plain local address. Anything else came in through a public name."""
    return (host or "").rsplit(":", 1)[0].lower() in LOCAL_NAMES


def key_ok(expected: str | None, supplied: str | None) -> bool:
    """Constant-time compare. No key set means everyone is let in (local use)."""
    if not expected:
        return True
    return hmac.compare_digest((supplied or "").encode(), expected.encode())


def parse_cookies(header: str | None) -> dict[str, str]:
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(header or "")
    except Exception:  # a broken Cookie header is just "no cookies"
        return {}
    return {name: morsel.value for name, morsel in jar.items()}


def cookie_header(name: str, value: str, secure: bool) -> str:
    """HttpOnly (scripts cannot read it) and SameSite=Strict (other sites cannot send it)."""
    text = f"{name}={value}; Path=/; HttpOnly; SameSite=Strict"
    return text + "; Secure" if secure else text
