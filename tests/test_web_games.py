"""Web play: access key, allowed hosts, one game per device, seats, idle expiry. No network."""

import json

import pytest
import typer
from helpers import SCENARIO
from web_helpers import SC, Client, game_server, patch_model, shut

from whisperwick import web_auth, web_play


@pytest.fixture
def make(monkeypatch, tmp_path):
    patch_model(monkeypatch)
    started = []

    def start(minutes=100, **options):
        server, manager = game_server(tmp_path, minutes, **options)
        started.append((server, manager))
        return server.server_address[1], manager

    yield start
    for server, manager in started:
        shut(server, manager)


# ---- the key ----


def test_key_is_required_and_the_cookie_then_works(make):
    port, manager = make(key="s3cret")
    c = Client(port)
    code, body = c.request("/")
    assert code == 403 and b"Ask for the link with the key." in body
    assert c.request("/?key=wrong")[0] == 403
    assert c.request("/state")[0] == 403 and c.request("/act", {"action": "look"})[0] == 403
    assert manager.games == {}  # no game was created for any of that
    # The right key sets an HttpOnly, SameSite=Strict cookie and sends the page back to "/".
    code, _ = c.request("/?key=s3cret")
    assert code == 302 and c.last.getheader("Location") == "/"
    set_cookie = c.last.getheader("Set-Cookie")
    assert "HttpOnly" in set_cookie and "SameSite=Strict" in set_cookie
    assert c.request("/")[0] == 200 and len(manager.games) == 1
    assert c.until(lambda s: s["awaiting"])["you"]["place"]["id"] == "loc_market"


def test_key_is_compared_in_constant_time(make, monkeypatch):
    seen = []
    real = web_auth.hmac.compare_digest
    monkeypatch.setattr(web_auth.hmac, "compare_digest", lambda a, b: seen.append(1) or real(a, b))
    port, _ = make(key="k")
    Client(port).request("/?key=k")
    assert seen
    assert web_auth.key_ok("k", "k") and not web_auth.key_ok("k", None)
    assert web_auth.key_ok(None, None)  # no key set: local use as before


def test_no_key_means_as_before(make):
    port, _ = make()
    c = Client(port)
    assert c.request("/")[0] == 200
    assert "Secure" not in c.last.getheader("Set-Cookie")  # plain local http


# ---- allowed hosts ----


def test_allow_host_is_accepted_with_or_without_port(make):
    port, _ = make(key="k", allow_hosts=("box.ts.net",))
    c = Client(port)
    c.request("/?key=k")
    for host in ("box.ts.net", "box.ts.net:443", f"box.ts.net:{port}", f"localhost:{port}"):
        assert c.request("/state", headers={"Host": host})[0] == 200
    assert c.request("/state", headers={"Host": "other.ts.net"})[0] == 403
    # Through the public name the cookies are Secure.
    fresh = Client(port)
    fresh.request("/?key=k", headers={"Host": "box.ts.net"})
    assert "Secure" in fresh.last.getheader("Set-Cookie")


def test_allow_host_without_key_is_refused(tmp_path):
    with pytest.raises(typer.Exit):
        web_play.serve(SC, SCENARIO, str(tmp_path / "x.db"), None, 5, 0, None, ("box.ts.net",))


# ---- one game per device ----


def test_two_browsers_get_independent_games(make):
    port, manager = make()
    a, b = Client(port), Client(port)
    a.request("/")
    b.request("/")
    assert a.cookies["ww_game"] != b.cookies["ww_game"] and len(manager.games) == 2
    a.until(lambda s: s["awaiting"])
    b.until(lambda s: s["awaiting"])
    a.request("/act", {"action": "talk", "target": "npc_bob", "message": "only in game A"})
    a.until(lambda s: s["awaiting"] and any("only in game A" in x for x in s["feed"]))
    assert "only in game A" not in json.dumps(b.state())
    # Each game has its own database file.
    assert len({g.player for g in manager.games.values()}) == 2


def test_max_games_gives_a_friendly_503(make):
    port, _ = make(max_games=2)
    for _ in range(2):
        assert Client(port).request("/")[0] == 200
    code, body = Client(port).request("/")
    assert code == 503 and b"All seats are taken" in body


def test_idle_games_are_stopped_and_free_their_seat(make):
    now = [0.0]
    port, manager = make(max_games=1, idle_seconds=60)
    manager.clock = lambda: now[0]
    a = Client(port)
    a.request("/")
    old = a.cookies["ww_game"]
    now[0] = 30
    assert Client(port).request("/")[0] == 503  # still taken
    assert a.state()["awaiting"] is not None  # a visit keeps it alive
    now[0] = 80  # 50 s after that visit: not idle for 60 s yet
    assert Client(port).request("/")[0] == 503
    now[0] = 200  # idle for more than 60 s
    assert a.state() == {"gone": True}  # expired: stopped, and the page will reload
    assert Client(port).request("/")[0] == 200 and old not in manager.games


def test_new_game_replaces_the_callers_game(make):
    port, manager = make(max_games=1)
    c = Client(port)
    c.request("/")
    old = c.cookies["ww_game"]
    c.until(lambda s: s["awaiting"])
    assert c.request("/newgame", {})[0] == 200
    assert c.cookies["ww_game"] != old and list(manager.games) == [c.cookies["ww_game"]]
    assert c.until(lambda s: s["awaiting"])["feed_total"] >= 0
    # An unknown cookie gets "gone" on state, and a fresh game on the page.
    ghost = Client(port)
    ghost.cookies["ww_game"] = "nope"
    assert ghost.state() == {"gone": True}
    assert ghost.request("/quit", {})[0] == 409
