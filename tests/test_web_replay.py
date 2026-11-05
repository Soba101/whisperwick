"""Replay requests use real auth and game lookup, without sockets or model calls."""

import json
import re
import threading

import pytest
from invite_helpers import request
from web_helpers import SC

from whisperwick.events import Event
from whisperwick.invite_players import Players
from whisperwick.player_web import WebPlayer
from whisperwick.scenario import build_world
from whisperwick.web_games import GameManager


@pytest.fixture
def setup(tmp_path):
    worlds = []

    def launch(player_name="owner"):
        sc = SC.model_copy(deep=True)
        # A changed name catches accidental use of the default scenario on the server.
        next(n for n in sc.npcs if n.id == "npc_bob").name = player_name + "'s Bob"
        player = WebPlayer(sc)
        world = build_world(sc, str(tmp_path / f"game-{len(worlds)}.db"))
        worlds.append(world)
        claim = {"kind": "accuses", "subject": "npc_victor"}
        for actor, target in (("npc_bob", "npc_alice"), ("npc_alice", "npc_hal")):
            world.log.append(Event(
                tick=world.clock.tick, type="talk", actor=actor, location="loc_inn",
                data={"to": target, "message": f"{player_name}'s private story {len(worlds)}",
                      "claim": claim},
            ))
        with player.cv:
            player._refresh(world)
        # No game thread or model is needed to exercise the HTTP handler.
        return player, threading.Thread()

    store, games = Players(tmp_path / "access"), GameManager(launch)
    yield store, games
    games.close_all()
    for world in worlds:
        world.log.db.close()


def replay(store, games, game, **options):
    return request(store, games, "/replay", token=game.token, **options)


def data_from(response):
    raw = re.search(rb'id="run">(.*?)</script>', response["body"], re.S).group(1)
    return json.loads(raw)


def test_replay_is_hidden_until_finished_and_returns_own_log_read_only(setup, tmp_path):
    store, games = setup
    game = games.open(None, "owner")
    assert replay(store, games, game, key="owner-secret")["code"] == 404
    game.player.finish()
    # Finished is the gate, including the time before the private accusation is chosen.
    assert game.player.ending.accusation is None
    world = game.player.world
    before = world.state_hash(), world.log.all(), set(tmp_path.rglob("*"))
    result = replay(store, games, game, key="owner-secret")
    assert result["code"] == 200 and result["body"].startswith(b"<!doctype html>")
    assert result["headers"]["Content-Type"] == "text/html; charset=utf-8"
    assert result["headers"]["Cache-Control"] == "no-store"
    data = data_from(result)
    assert data["names"]["npc_bob"] == "owner's Bob"
    assert [(e["actor"], e["to"]) for e in data["events"]] == [
        ("npc_bob", "npc_alice"), ("npc_alice", "npc_hal")]
    assert all(e["text"] == "owner's private story 1" and e["claim"] for e in data["events"])
    assert data["thoughts"] == []
    assert (world.state_hash(), world.log.all(), set(tmp_path.rglob("*"))) == before


def test_other_browser_gets_only_its_own_replay_and_cannot_select_a_run(setup):
    store, games = setup
    # Local browsers share no named identity; their cookies still select separate games.
    a, b = games.open(None), games.open(None)
    a.player.finish()
    assert replay(store, games, b, key="owner-secret")["code"] == 404
    for token in (None, "unknown", b.token):
        path = f"/replay?game_id={a.token}&db=game-0.db"
        assert request(store, games, path, key="owner-secret", token=token)["code"] == 404
    b.player.finish()
    a_data = data_from(replay(store, games, a, key="owner-secret"))
    b_data = data_from(replay(store, games, b, key="owner-secret"))
    assert all(e["text"] == "owner's private story 1" for e in a_data["events"])
    assert all(e["text"] == "owner's private story 2" for e in b_data["events"])
    games.discard(a.token)
    assert replay(store, games, a, key="owner-secret")["code"] == 404
    assert replay(store, games, b, key="owner-secret")["code"] == 200


def test_named_player_cannot_use_another_players_game_cookie(setup):
    store, games = setup
    alice, bob = store.invite("Alice"), store.invite("Bob")
    game = games.open(None, "Alice")
    game.player.finish()
    assert replay(store, games, game, key=bob)["code"] == 404
    assert replay(store, games, game, key=alice)["code"] == 200


@pytest.mark.parametrize("key", [None, "wrong"])
def test_key_cookie_is_required_even_with_a_finished_game(setup, key):
    store, games = setup
    game = games.open(None, "owner")
    game.player.finish()
    response = replay(store, games, game, key=key)
    assert response["code"] == 403 and json.loads(response["body"]) == {"error": "key needed"}
    # A key in the replay URL does not replace the required cookie.
    response = request(store, games, "/replay?key=owner-secret", token=game.token)
    assert response["code"] == 403


def test_bad_host_is_refused_before_replay(setup):
    store, games = setup
    game = games.open(None, "owner")
    game.player.finish()
    assert replay(store, games, game, key="owner-secret", host="evil.test")["code"] == 403
