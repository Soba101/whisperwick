"""The public form is offline, bounded, generic and protected by existing HTTP rules."""

import re
from concurrent.futures import ThreadPoolExecutor

import pytest
from invite_helpers import manager, request

from whisperwick.invite_files import rows
from whisperwick.invite_players import Players
from whisperwick.invite_requests import Requests


@pytest.fixture
def setup(tmp_path):
    store, games = Players(tmp_path), manager()
    return store, games, Requests(tmp_path)


def test_locked_pages_are_offline_and_do_not_start_games(setup):
    store, games, _ = setup
    for path in ("/", "/3d"):
        page = request(store, games, path)["body"].decode()
        assert '<form id="request">' in page and "fetch('/request'" in page
        assert not re.search(r"https?://|src=|href=|@import", page)
    assert games.games == {}


@pytest.mark.parametrize("body", [
    {}, {"name": ""}, {"name": " "}, {"name": None}, {"name": 3}, {"name": []},
    {"name": "A" * 41}, {"name": "Alice1"}, {"name": "A\nB"}, {"name": "<script>"},
    {"name": "Alice", "note": "x" * 301}, {"name": "Alice", "note": None},
    {"name": "Alice", "player": "forged"},
])
def test_validation_does_not_save(setup, body):
    store, games, waiting = setup
    assert request(store, games, "/request", body, waiting=waiting)["code"] == 400
    assert not waiting.path.exists()


def test_duplicates_update_note_without_name_enumeration(setup):
    store, games, waiting = setup
    for name, note in (("Élodie O'Brien-Smith.", "x" * 300), ("ÉLODIE O'BRIEN-SMITH.", "New")):
        result = request(store, games, "/request", {"name": name, "note": note}, waiting=waiting)
        assert (result["code"], result["body"]) == (200, b"Request sent")
    entry, = rows(waiting.path)
    assert set(entry) == {"time", "name", "note"} and entry["note"] == "New"
    assert request(store, games, "/request", {"name": "A" * 40})["body"] == b"Request sent"


def test_full_queue_same_response_for_existing_and_new_names(setup):
    store, games, waiting = setup
    for i in range(20):
        assert waiting.save({"name": "Player " + chr(65 + i)})[0] == 200
    for name in ("Player A", "New Name"):
        result = request(store, games, "/request", {"name": name}, waiting=waiting)
        assert result["code"] == 429 and b"full" in result["body"]
    assert len(rows(waiting.path)) == 20


def test_global_sliding_limit_including_invalid_posts(setup):
    store, games, _ = setup
    tick = [0.0]
    waiting = Requests(store.folder, clock=lambda: tick[0])
    for _ in range(10):
        assert request(store, games, "/request", {}, waiting=waiting)["code"] == 400
    assert request(store, games, "/request", {"name": "Alice"}, waiting=waiting)["code"] == 429
    tick[0] = 60
    assert request(store, games, "/request", {"name": "Alice"}, waiting=waiting)["code"] == 200


def test_concurrent_posts_stay_within_rate_limit(setup):
    store, games, waiting = setup
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda _: request(store, games, "/request", {"name": "Alice"},
                                               waiting=waiting)["code"], range(24)))
    assert codes.count(200) == 10 and codes.count(429) == 14
    assert len(rows(waiting.path)) == 1


@pytest.mark.parametrize("options", [
    {"kind": "text/plain"}, {"kind": "application/x-www-form-urlencoded"},
    {"length": 20001}, {"length": -1}, {"raw": b"{"}, {"raw": b"[]"},
    {"raw": b"\xff"},
])
def test_request_uses_same_json_and_body_rules(setup, options):
    store, games, _ = setup
    assert request(store, games, "/request", {"name": "Alice"}, **options)["code"] == 400
    assert not (store.folder / "requests.jsonl").exists()
    assert request(store, games, "/request", {"name": "Alice"}, host="evil.test")["code"] == 403


def test_existing_players_receive_the_same_request_response(setup):
    store, games, waiting = setup
    store.invite("Alice")
    for name in ("Alice", "Nobody"):
        result = request(store, games, "/request", {"name": name}, waiting=waiting)
        assert (result["code"], result["body"]) == (200, b"Request sent")


def test_failed_atomic_write_preserves_waiting_requests(setup, monkeypatch):
    from whisperwick import invite_files

    _, _, waiting = setup
    assert waiting.save({"name": "Alice", "note": "Before"})[0] == 200
    before = waiting.path.read_bytes()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(invite_files.os, "replace", fail)
    assert waiting.save({"name": "Bob"})[0] == 500
    assert waiting.path.read_bytes() == before
    assert not list(waiting.folder.glob(".invite-*"))
