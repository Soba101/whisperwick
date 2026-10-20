"""Owner admin routes: owner-only, CSRF-guarded, secrets stored as hashes, offline pages."""

import json
import re
import threading

import pytest
from invite_helpers import manager, request
from web_helpers import SC

from whisperwick.invite_players import Players, key_hash
from whisperwick.invite_requests import Requests
from whisperwick.player_web import WebPlayer
from whisperwick.web_admin import ACTIONS, CSRF_HEADER, CSRF_TOKEN
from whisperwick.web_games import GameManager
from whisperwick.web_page import render_page

OWNER = "owner-secret"
GOOD = {CSRF_HEADER: CSRF_TOKEN}


def post(store, games, path, body, key=OWNER, headers=GOOD, **kw):
    return request(store, games, path, body, key=key, headers=headers, **kw)


def test_admin_page_is_owner_only(tmp_path):
    store, games = Players(tmp_path), manager()
    player = store.invite("Alice")
    page = request(store, games, "/admin", key=OWNER)
    assert page["code"] == 200 and b'name="csrf-token"' in page["body"]
    for key in (player, None, "wrong"):
        denied = request(store, games, "/admin", key=key)
        assert denied["code"] == 404
        assert b"admin" not in denied["body"].lower()


@pytest.mark.parametrize("path", sorted(ACTIONS))
def test_non_owner_posts_get_404(tmp_path, path):
    store, games = Players(tmp_path), manager()
    player = store.invite("Alice")
    for key in (player, None):
        assert post(store, games, path, {"name": "x"}, key=key)["code"] == 404


def test_csrf_and_content_type(tmp_path):
    store, games = Players(tmp_path), manager()
    body = {"name": "Bo"}
    assert post(store, games, "/admin/invite", body, headers={})["code"] == 403
    assert post(store, games, "/admin/invite", body, headers={CSRF_HEADER: "bad"})["code"] == 403
    assert post(store, games, "/admin/invite", body, kind="text/plain")["code"] == 400


def test_approve_and_invite_store_only_hashes(tmp_path):
    store, games = Players(tmp_path), manager()
    waiting = Requests(tmp_path)
    waiting.save({"name": "Cara", "note": "hi"})
    result = post(store, games, "/admin/approve", {"name": "Cara"}, waiting=waiting)
    key = json.loads(result["body"])["link"].split("?key=")[1]
    assert result["code"] == 200
    assert key_hash(key) in (tmp_path / "players.json").read_text()
    assert not waiting.path.read_text().strip()
    assert post(store, games, "/admin/approve", {"name": "Cara"}, waiting=waiting)["code"] == 400
    other = json.loads(post(store, games, "/admin/invite", {"name": "Dee"})["body"])["link"]
    key2 = other.split("?key=")[1]
    assert "?key=" in other and key_hash(key2) in (tmp_path / "players.json").read_text()
    for f in tmp_path.iterdir():
        assert key not in f.read_text() and key2 not in f.read_text()


def test_decline_removes_request(tmp_path):
    store, games = Players(tmp_path), manager()
    waiting = Requests(tmp_path)
    waiting.save({"name": "Cara"})
    assert post(store, games, "/admin/decline", {"name": "Cara"}, waiting=waiting)["code"] == 200
    assert not waiting.path.read_text().strip()


def test_revoke_locks_key_and_frees_seat(tmp_path):
    store, games = Players(tmp_path), manager()
    key = store.invite("Alice")
    request(store, games, key=key)
    assert len(games.active()) == 1
    assert post(store, games, "/admin/revoke", {"name": "alice"})["code"] == 200
    assert request(store, games, key=key)["code"] == 403
    assert games.active() == [] and games.games == {}


def test_stop_by_id(tmp_path):
    store, games = Players(tmp_path), manager()
    request(store, games, key=store.invite("Alice"))
    game_id = games.active()[0]["id"]
    assert post(store, games, "/admin/stop", {"id": game_id})["code"] == 200
    assert games.active() == []
    assert post(store, games, "/admin/stop", {"id": "nope"})["code"] == 400


def test_pages_are_offline_and_escape_saved_text(tmp_path):
    store, games = Players(tmp_path), manager()
    Requests(tmp_path).save({"name": "Cara", "note": "<script>x()</script>"})
    (tmp_path / "feedback.jsonl").write_text(json.dumps({"player": "Fiona"}) + "\n")
    admin = request(store, games, "/admin", key=OWNER)["body"].decode()
    assert "Fiona" in admin and "&lt;script&gt;x()" in admin and "<script>x()" not in admin
    for html in (admin, render_page(admin=True)):
        assert not re.search(r'(src|href)="(http|//)', html)


def test_admin_link_only_for_owner(tmp_path):
    store = Players(tmp_path)

    def launch(role=None, player_name="owner"):
        return WebPlayer(SC), threading.Thread()

    games = GameManager(launch, choose_roles=True)
    player = store.invite("Alice")
    assert b'href="/admin"' in request(store, games, key=OWNER)["body"]
    assert b'href="/admin"' not in request(store, games, key=player)["body"]
