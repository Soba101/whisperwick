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
    """Local names with our port, plus bare allowed names that accept any port."""
    hosts = {f"{n}:{port}" for n in LOCAL_NAMES}
    hosts.update(name.lower() for name in names)
    return hosts


def host_allowed(host: str | None, hosts: set[str]) -> bool:
    """Accept allowed names with any port, and local names only with our port."""
    host = (host or "").lower()
    # A proxy (e.g. Funnel on 8443) may put any port after the public name. Local names
    # are stored with our port, so the bare-name check below never matches them.
    return host in hosts or host.rsplit(":", 1)[0] in hosts


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
    """HttpOnly (scripts cannot read it) and SameSite=Lax.

    Lax, not Strict: a link tapped in another app (e.g. a chat app) starts a cross-site visit, and
    Strict then drops the cookie on the redirect to "/", so the player saw "Ask for the link with
    the key". Lax still keeps the cookie off other sites' POSTs, so no other page can act in a game.
    """
    text = f"{name}={value}; Path=/; HttpOnly; SameSite=Lax"
    return text + "; Secure" if secure else text
