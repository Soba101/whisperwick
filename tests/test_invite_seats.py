"""Named games replace old browsers, preserve isolation, and free seats."""

import json

from invite_helpers import manager, request
from typer.testing import CliRunner

from whisperwick.cli import app
from whisperwick.invite_players import Players
from whisperwick.web_page import render_page


def test_five_seats_sixth_refused_and_second_browser_replaces(tmp_path):
    store, games = Players(tmp_path), manager()
    keys = [store.invite("Player " + chr(65 + i)) for i in range(6)]
    for i, key in enumerate(keys[:5], 1):
        page = request(store, games, key=key)
        assert page["code"] == 200 and f"Seat {i} of 5".encode() in page["body"]
    assert request(store, games, key=keys[5])["code"] == 503
    first = next(iter(games.games.values()))
    assert first.name == first.player.name == "Player A"
    assert request(store, games, key=keys[0])["code"] == 200
    assert first.player.stopped and games.get(first.token, first.name) is None
    assert len(games.games) == 5
    player, *_ = store.read()
    assert player["games"] == 2 and player["last_seen"]
    result = request(store, games, "/state", key=keys[1], token=first.token)
    assert result["body"] == b'{"gone": true}'


def test_player_cannot_read_replace_or_discard_another_players_game(tmp_path):
    store, games = Players(tmp_path), manager()
    alice, bob = store.invite("Alice"), store.invite("Bob")
    request(store, games, key=alice)
    game = next(iter(games.games.values()))
    assert request(store, games, "/state", key=bob, token=game.token)["body"] == b'{"gone": true}'
    result = request(store, games, "/feedback", {"page": "2d"}, key=bob, token=game.token)
    assert result["code"] == 409
    request(store, games, "/choose", {}, key=bob, token=game.token)
    assert games.get(game.token, "Alice") is game
    request(store, games, "/newgame", {}, key=bob, token=game.token)
    assert games.get(game.token, "Alice") is game and len(games.games) == 2


def test_finished_and_idle_games_free_seats():
    tick = [0]
    games = manager(max_games=1, idle_seconds=10, clock=lambda: tick[0])
    first = games.open(None, "Alice")
    assert games.open(None, "Bob") is None
    first.player.finished = True
    second = games.open(None, "Bob")
    assert second is not None
    tick[0] = 11
    assert games.open(None, "Cara") is not None
    assert first.player.stopped and second.player.stopped


def test_named_welcome_in_both_views_and_feedback(tmp_path):
    store, games = Players(tmp_path), manager()
    key = store.invite("Alice")
    page = request(store, games, "/3d", key=key)
    assert b"Welcome, Alice" in page["body"] and b"Seat 1 of 5" in page["body"]
    game = next(iter(games.games.values()))
    game.player.feedback_path = tmp_path / "feedback.jsonl"
    result = request(store, games, "/feedback", {"page": "2d"}, key=key, token=game.token)
    assert result["code"] == 200
    assert json.loads(game.player.feedback_path.read_text())["player"] == "Alice"
    assert request(store, games, key="owner-secret")["body"].count(b"Welcome, owner") == 2
    assert "Welcome, &lt;bad&gt;" in render_page("<bad>")


def test_max_games_option_is_positive():
    assert CliRunner().invoke(app, ["play", "--web", "--max-games", "0"]).exit_code != 0
