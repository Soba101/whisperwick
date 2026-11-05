"""Per-client and overall limits on the request form, and the owner's Clear all."""

import json
from collections import deque

from invite_helpers import manager, request

from whisperwick.invite_players import Players
from whisperwick.invite_requests import MAX_CLIENTS, OVERALL_LIMIT, Requests
from whisperwick.web_admin import CSRF_HEADER, CSRF_TOKEN
from whisperwick.web_auth import client_id


def test_one_client_does_not_block_another(tmp_path):
    tick = [0.0]
    r = Requests(tmp_path, clock=lambda: tick[0])
    assert all(r.allow("a") for _ in range(10))
    assert not r.allow("a")
    assert r.allow("b")
    tick[0] = 61  # the window passes
    assert r.allow("a")


def test_overall_ceiling_and_client_cap(tmp_path):
    r = Requests(tmp_path, clock=lambda: 0.0)
    allowed = sum(r.allow(f"c{i}") for i in range(OVERALL_LIMIT + 20))
    assert allowed == OVERALL_LIMIT
    # New clients are refused once too many are tracked.
    r = Requests(tmp_path, clock=lambda: 0.0)
    r.attempts = {f"x{i}": deque([0.0]) for i in range(MAX_CLIENTS)}
    assert not r.allow("new") and r.allow("x1")


def test_forwarded_header_only_from_loopback():
    assert client_id("127.0.0.1", "9.9.9.9, 1.2.3.4") == "1.2.3.4"
    assert client_id("::1", "1.2.3.4") == "1.2.3.4"
    assert client_id("127.0.0.1", None) == "127.0.0.1"
    assert client_id("8.8.8.8", "1.2.3.4") == "8.8.8.8"


def test_http_limit_is_per_forwarded_client(tmp_path):
    store, games = Players(tmp_path), manager()
    waiting = Requests(tmp_path, clock=lambda: 0.0)

    def send(xff, peer="127.0.0.1"):
        return request(store, games, "/request/code", {"code": "x"}, waiting=waiting,
                       headers={"X-Forwarded-For": xff}, peer=peer)["code"]

    assert all(send("1.1.1.1") == 400 for _ in range(10))
    assert send("1.1.1.1") == 429 and send("2.2.2.2") == 400
    # A direct peer cannot dodge its limit by forging the header.
    assert all(send(f"f{i}", peer="8.8.8.8") == 400 for i in range(10))
    assert send("fresh", peer="8.8.8.8") == 429


def test_admin_clear(tmp_path):
    store, games = Players(tmp_path), manager()
    waiting = Requests(tmp_path)
    waiting.save({"name": "Cara"})
    waiting.save({"name": "Dee"})
    go = lambda **kw: request(store, games, "/admin/clear", {}, waiting=waiting,  # noqa: E731
                              **{"key": "owner-secret", **kw})
    assert go(headers={})["code"] == 403  # no CSRF header
    assert go(key="nobody", headers={CSRF_HEADER: CSRF_TOKEN})["code"] == 404  # not the owner
    assert waiting.path.read_text().strip()
    ok = go(headers={CSRF_HEADER: CSRF_TOKEN})
    assert ok["code"] == 200 and json.loads(ok["body"]) == {"ok": True}
    assert not waiting.path.read_text().strip()
