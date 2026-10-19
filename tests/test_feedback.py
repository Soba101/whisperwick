"""Feedback stays private, bounded, authenticated, and separate from game events."""

import hashlib
import json
import threading
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

import pytest
from helpers import fresh_world
from typer.testing import CliRunner
from web_helpers import SC

from whisperwick import feedback
from whisperwick.cli import app
from whisperwick.player_web import WebPlayer
from whisperwick.web_games import Game
from whisperwick.web_server import Handler


@pytest.fixture
def game(tmp_path):
    player = WebPlayer(SC)
    player._refresh(fresh_world())
    player.feedback_path = tmp_path / "data" / "feedback.jsonl"
    return Game("private-cookie", player, threading.Thread(), 0)


def post(game, body, *, authorized=True, host=True, seat=True):
    # Use the real POST handler without needing permission to bind a socket.
    h = object.__new__(Handler)
    h.path = "/feedback"
    h.host_ok = lambda: host
    h.key_cookie_ok = lambda: authorized
    h.cookies = lambda: {"ww_game": game.token}
    h.games = SimpleNamespace(get=lambda token: game if seat else None)
    raw = json.dumps(body).encode()
    h.headers = {"Content-Type": "application/json", "Content-Length": str(len(raw))}
    h.rfile, h.wfile = BytesIO(raw), BytesIO()
    result = {}
    h.send_response = lambda code: result.update(code=code)
    h.send_header = lambda *args: None
    h.end_headers = lambda: None
    h.do_POST()
    return result["code"], json.loads(h.wfile.getvalue())


def test_saving_is_private_and_has_server_context(game):
    before = [e.model_dump() for e in game.player.world.log.all()]
    inbox = list(game.player.inbox)
    text = 'Private feedback with a newline\nand <script>markup</script>'
    body = {"page": "3d", "rating": 5, "tags": ["bug", "loved it"], "text": text}
    assert post(game, body) == (200, {"ok": True})
    lines = game.player.feedback_path.read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert all(entry[key] == value for key, value in body.items())
    assert entry["game_id"] == hashlib.sha256(game.token.encode()).hexdigest()
    assert entry["crime"] == SC.crime_seed and entry["role"] == SC.role_id
    assert entry["clock"] == game.player.view["clock"]
    assert datetime.fromisoformat(entry["time"]).utcoffset().total_seconds() == 0
    assert [e.model_dump() for e in game.player.world.log.all()] == before
    assert list(game.player.inbox) == inbox
    assert text not in json.dumps(game.player.snapshot())


@pytest.mark.parametrize("change", [
    {"page": "other"}, {"page": []}, {"rating": True}, {"rating": 0}, {"rating": 6},
    {"rating": 1.0}, {"rating": "5"}, {"rating": []}, {"text": 3}, {"text": None},
    {"text": "x" * 2001}, {"tags": "bug"}, {"tags": ["unknown"]}, {"tags": [{}]},
    {"tags": ["bug", "bug"]}, {"game_id": "forged"},
])
def test_invalid_feedback_is_not_saved(game, change):
    assert post(game, {"page": "2d", **change})[0] == 400
    assert not game.player.feedback_path.exists()
    assert game.feedback_count == 0


@pytest.mark.parametrize("rating", [None, "", 1, 5])
def test_optional_fields_and_text_boundary(game, rating):
    assert post(game, {"page": "2d", "rating": rating, "text": "x" * 2000})[0] == 200
    assert post(game, {"page": "2d"})[0] == 200


def test_auth_and_game_required(game):
    for options in ({"authorized": False}, {"host": False}):
        assert post(game, {"page": "2d"}, **options)[0] == 403
    assert post(game, {"page": "2d"}, seat=False)[0] == 409
    assert not game.player.feedback_path.exists()


def test_limit_shared_across_views_and_concurrent_posts(game):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda i: post(game, {"page": "3d" if i % 2 else "2d"})[0],
                              range(20)))
    assert codes.count(200) == 10 and codes.count(429) == 10
    assert len(game.player.feedback_path.read_text().splitlines()) == 10


def test_cli_newest_first_and_last(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, ["feedback"]).output == "No feedback saved.\n"
    feedback.DEFAULT_PATH.parent.mkdir()
    lines = [json.dumps({"text": str(n)}) for n in range(3)]
    feedback.DEFAULT_PATH.write_text("\n".join(lines) + "\n")
    result = runner.invoke(app, ["feedback", "--last", "2"])
    assert result.exit_code == 0
    assert [json.loads(line)["text"] for line in result.output.splitlines()] == ["2", "1"]
    assert len(runner.invoke(app, ["feedback"]).output.splitlines()) == 3
    assert runner.invoke(app, ["feedback", "--last", "0"]).exit_code != 0


def test_shared_dialog_is_offline_in_2d_and_served_in_3d():
    from whisperwick.web3d_assets import asset
    from whisperwick.web_page import render_page

    page = render_page()
    assert page.count("<button data-feedback>Feedback</button>") == 2
    assert "setupFeedback('2d')" in page and "Thanks, saved." in page
    assert 'src=' not in page and 'href=' not in page
    assert "https://" not in page and "http://" not in page
    assert "data-feedback" in asset("index.html")[0].decode()
    assert "setupFeedback('3d', fixture)" in asset("app.js")[0].decode()
    assert "Feedback" in asset("ending.js")[0].decode()
    assert asset("feedback.js")[1].startswith("text/javascript")
    assert asset("feedback.css")[1].startswith("text/css")


def test_failed_write_does_not_spend_allowance(game, tmp_path):
    blocked = tmp_path / "not-a-folder"
    blocked.write_text("occupied")
    game.player.feedback_path = blocked / "feedback.jsonl"
    assert post(game, {"page": "2d"})[0] == 500
    assert game.feedback_count == 0


def test_launcher_saves_beside_run_database(tmp_path, monkeypatch):
    from whisperwick import web_play

    monkeypatch.setattr(web_play, "run_with_llm", lambda *args, **kwargs: None)
    launch = web_play.launcher(SC, tmp_path / "scenario.yaml",
                               lambda n: str(tmp_path / "runs" / f"{n}.db"), None, 1)
    player, thread = launch()
    thread.join(timeout=2)
    assert player.feedback_path == tmp_path / "runs" / "feedback.jsonl"
