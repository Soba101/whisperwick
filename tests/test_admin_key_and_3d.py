"""2026-10-21: a separate admin key, and 3D as the main view once a game exists."""

from invite_helpers import manager, request

from whisperwick import web_auth
from whisperwick.invite_players import Players

OWNER, ADMIN = "owner-secret", "admin-secret"


def test_with_an_admin_key_the_play_link_no_longer_opens_admin(tmp_path):
    store, games = Players(tmp_path), manager()
    assert request(store, games, "/admin", key=OWNER, admin_key=ADMIN)["code"] == 404
    assert request(store, games, "/admin", key=OWNER, admin_key=ADMIN, admin="wrong")["code"] == 404
    assert request(store, games, "/admin", admin_key=ADMIN, admin=ADMIN)["code"] == 200


def test_admin_link_sets_its_cookie_and_drops_the_key(tmp_path):
    store, games = Players(tmp_path), manager()
    r = request(store, games, f"/admin?key={ADMIN}", admin_key=ADMIN)
    assert r["code"] == 302 and r["headers"]["Location"] == "/admin"
    assert r["headers"]["Set-Cookie"].startswith(web_auth.ADMIN_COOKIE + "=")
    # A wrong key on the admin link shows nothing.
    assert request(store, games, "/admin?key=nope", admin_key=ADMIN)["code"] == 404


def test_without_an_admin_key_the_owner_key_still_manages(tmp_path):
    store, games = Players(tmp_path), manager()
    assert request(store, games, "/admin", key=OWNER)["code"] == 200


def test_home_goes_to_3d_once_a_game_exists(tmp_path):
    store, games = Players(tmp_path), manager()
    game = games.open(None, "owner")
    r = request(store, games, "/", key=OWNER, token=game.token)
    assert r["code"] == 302 and r["headers"]["Location"] == "/3d"
    assert request(store, games, "/?view=2d", key=OWNER, token=game.token)["code"] == 200
