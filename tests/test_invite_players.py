"""Private keys, immediate revocation, owner access and CLI management."""

import base64
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie

import pytest
from invite_helpers import manager, request
from typer.testing import CliRunner

from whisperwick.cli import app
from whisperwick.invite_files import rows
from whisperwick.invite_players import Players
from whisperwick.invite_requests import Requests


@pytest.fixture
def store(tmp_path):
    return Players(tmp_path / "data")


def test_keys_on_disk_and_case_insensitive_unique_names(store):
    # Since 2026-10-21 the raw key is stored so the owner page can copy the link again.
    key = store.invite("Alice")
    assert len(base64.urlsafe_b64decode(key + "=")) == 32
    player, = store.read()
    assert player == {"name": "Alice", "key_hash": hashlib.sha256(key.encode()).hexdigest(),
                      "key": key, "created": player["created"], "last_seen": None, "games": 0,
                      "revoked": False}
    with pytest.raises(ValueError, match="already exists"):
        store.invite("ALICE")
    with pytest.raises(ValueError, match="reserved"):
        store.invite("owner")


def test_owner_player_redirect_cookie_and_revocation(store):
    key, games = store.invite("Alice"), manager()
    for path in ("/", "/3d"):
        result = request(store, games, path + "?key=" + key)
        assert result["code"] == 302 and result["headers"]["Location"] == path
        cookie = result["headers"]["Set-Cookie"]
        assert SimpleCookie(cookie)["ww_key"].value == key
        assert all(rule in cookie for rule in ("Secure", "HttpOnly", "SameSite=Lax", "Path=/"))
        assert result["headers"]["Referrer-Policy"] == "no-referrer"
    page = request(store, games, key=key)
    assert page["code"] == 200 and b"Welcome, Alice" in page["body"]
    assert b"Seat 1 of 5" in page["body"]
    # Revocation by another process invalidates the existing server's cache.
    Players(store.folder).revoke("ALICE")
    for path in ("/", "/3d", "/state", "/web3d/app.js", "/?key=" + key):
        assert request(store, games, path, key=key)["code"] == 403
    assert request(store, games, "/quit", {}, key=key)["code"] == 403
    assert request(store, games, key="owner-secret")["code"] == 200
    assert request(store, games, "/?key=owner-secret")["code"] == 302
    assert request(store, games, "/?key=" + key, host="evil.test")["code"] == 403


def test_changed_or_missing_file_fails_closed(store):
    key = store.invite("Alice")
    assert store.authenticate(key) == "Alice"
    store.path.write_text("not json")
    assert store.authenticate(key) is None
    store.path.unlink()
    assert store.authenticate(key) is None


def test_visits_and_games_are_not_lost_across_stores(store):
    store.invite("Alice")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: Players(store.folder).visit("Alice", True), range(16)))
    player, = store.read()
    assert player["games"] == 16 and player["last_seen"]


def test_commands_approve_remove_request_and_never_reprint_key(store, monkeypatch):
    monkeypatch.chdir(store.folder.parent)
    runner = CliRunner()
    assert Requests(store.folder).save({"name": "Alice", "note": "Hi"})[0] == 200
    assert "Alice" in runner.invoke(app, ["requests"]).output
    (store.folder / "invite-host.json").write_text(json.dumps("play.example:8443"))
    result = runner.invoke(app, ["invite", "--approve", "ALICE"])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("https://play.example:8443/?key=")
    key = result.output.strip().split("?key=")[1]
    assert rows(store.folder / "requests.jsonl") == []
    assert key not in runner.invoke(app, ["players"]).output
    assert "key_hash" not in runner.invoke(app, ["players"]).output
    assert runner.invoke(app, ["invite", "Alice"]).exit_code != 0
    assert runner.invoke(app, ["invite", "--approve", "Bob"]).exit_code != 0
    assert runner.invoke(app, ["revoke", "alice"]).exit_code == 0
    assert store.authenticate(key) is None
    assert runner.invoke(app, ["invite", "Bob", "--host", "other.example"]).output.startswith(
        "https://other.example/?key=")
    (store.folder / "invite-host.json").unlink()
    assert runner.invoke(app, ["invite", "Cara"]).output.startswith("https://YOUR-HOST/?key=")


def test_auth_cache_and_constant_time_hash_comparison(store, monkeypatch):
    from whisperwick import invite_players

    key = store.invite("Alice")
    reads, comparisons = [], []
    read, compare = store.read, invite_players.hmac.compare_digest
    monkeypatch.setattr(store, "read", lambda: reads.append(True) or read())
    monkeypatch.setattr(invite_players.hmac, "compare_digest",
                        lambda a, b: comparisons.append((a, b)) or compare(a, b))
    assert store.authenticate(key) == "Alice"
    assert store.authenticate(key) == "Alice"
    assert len(reads) == 1 and len(comparisons) == 2
    assert all(len(a) == len(b) == 64 and a != key for a, b in comparisons)
    # Even a damaged player registry cannot break the separate owner key.
    store.path.write_text("invalid")
    assert request(store, manager(), key="owner-secret")["code"] == 200


def test_server_remembers_default_host_and_keeps_local_cookie_rules(store, monkeypatch):
    from types import SimpleNamespace

    from whisperwick import web_server

    games = manager()
    monkeypatch.setattr(web_server, "LocalServer",
                        lambda *args: SimpleNamespace(server_address=("127.0.0.1", 8000)))
    server = web_server.make_server(games, 0, "owner-secret", ("play.example",), store)
    assert json.loads((store.folder / "invite-host.json").read_text()) == "play.example"
    assert server.RequestHandlerClass.players is store
    key = store.invite("Alice")
    result = request(store, games, "/?key=" + key, host="127.0.0.1:8000")
    assert result["code"] == 302 and "Secure" not in result["headers"]["Set-Cookie"]


def test_a_revoked_name_can_be_invited_again_and_the_old_key_stays_dead(tmp_path):
    store = Players(tmp_path)
    old = store.invite("Alice")
    with pytest.raises(ValueError, match="revoke them first"):
        store.invite("alice")
    store.revoke("Alice")
    new = store.invite("Alice")
    assert new != old
    assert store.authenticate(old) is None and store.authenticate(new) == "Alice"
    assert [p["name"] for p in store.read()].count("Alice") == 1


def test_revoke_removes_the_player_so_only_live_links_are_listed(tmp_path):
    store = Players(tmp_path)
    key = store.invite("Bob")
    store.revoke("Bob")
    assert store.authenticate(key) is None
    assert all(p["name"] != "Bob" for p in store.read())
