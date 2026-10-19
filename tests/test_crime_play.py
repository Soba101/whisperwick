"""Exercise play entry points, saved crime numbers and the shared web picker."""

import json
import shutil
import subprocess
import threading

import pytest
from helpers import SCENARIO, run_ticks
from test_play_terminal import fake_setup
from test_web_notebook import DOM
from test_web_roles import handler
from typer.testing import CliRunner

from whisperwick import cli, play_command, web_play
from whisperwick.crime import generate
from whisperwick.crime.selection import crime_number
from whisperwick.player_web import WebPlayer
from whisperwick.scenario import build_world, load_scenario
from whisperwick.web_ending import ENDING_JS
from whisperwick.web_games import GameManager
from whisperwick.web_js import JS


@pytest.mark.parametrize("choice", ["7", "random"])
def test_play_crime_number_saved_in_sidecar(monkeypatch, tmp_path, choice):
    fake_setup(monkeypatch)
    monkeypatch.setattr("whisperwick.crime.selection.os.urandom", lambda n: (7).to_bytes(n))
    db = tmp_path / "crime.db"
    result = CliRunner().invoke(
        cli.app, ["play", "--crime", choice, "--role", "cousin", "--db", str(db)], input="quit\n"
    )
    assert result.exit_code == 0, result.output
    assert "Crime #7" in result.output and "Bob's cousin" in result.output
    assert "who killed Bob?" in result.output
    saved = json.loads(db.with_suffix(".json").read_text())
    assert saved["crime_seed"] == saved["seed"] == 7
    assert saved["secrets"] == generate(7).secrets


def test_cli_crime_absent_has_old_start_and_events(monkeypatch):
    seen = []
    monkeypatch.setattr(play_command, "run_with_llm", lambda *a: seen.append(a[0]))
    result = CliRunner().invoke(cli.app, ["play"])
    assert result.exit_code == 0
    sc = seen[0]
    old = load_scenario(SCENARIO)
    assert sc == old and sc.crime_seed is None
    a, b = build_world(sc), build_world(old)
    assert run_ticks(a, 300) == run_ticks(b, 300)
    a.log.db.close()
    b.log.db.close()


def test_web_number_starts_generated_crime_and_keeps_role(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(web_play, "run_with_llm", lambda *a, **kw: seen.append(a))
    launch = web_play.launcher(
        load_scenario(SCENARIO), SCENARIO, lambda n: str(tmp_path / f"{n}.db"), None, 4320
    )
    games = GameManager(launch, choose_roles=True, choose_crimes=True)
    assert handler(games, "/state")[1]["default_crime"] == "random"
    assert handler(games, "/newgame", {"role": "partner", "crime": "7"})[0] == 200
    game = next(iter(games.games.values()))
    game.thread.join(2)
    sc = game.player.sc
    assert sc.crime_seed == 7 and sc.player_title == "Sarah's former business partner"
    assert seen[0][3:5] == (None, 4320)
    assert handler(games, "/newgame", {"crime": "oops"}, game.token)[0] == 400
    assert not game.player.stopped
    world = build_world(sc)
    player = WebPlayer(sc)
    with player.cv:
        player._refresh(world)
    state = player.snapshot()
    assert state["crime_seed"] == 7 and "Bob" in state["hook"]
    assert "murderer" not in state and "secrets" not in state
    player.finish()
    assert player.ending.choose("npc_sarah")
    assert player.snapshot()["ending"].startswith("Crime #7\n")
    world.log.db.close()


def test_web_zero_and_default_random():
    calls = []

    def launch(role, crime):
        calls.append(crime)
        return WebPlayer(generate(crime_number(crime))), threading.Thread()

    games = GameManager(launch, choose_roles=True, choose_crimes=True)
    assert handler(games, "/newgame", {"crime": 0})[0] == 200
    assert calls == ["0"]
    assert handler(games, "/newgame", {})[0] == 200
    assert calls[-1] == "random"


@pytest.mark.parametrize("bad", ["-1", "x", "1.5", True, [], "1" * 21])
def test_bad_numbers(bad):
    with pytest.raises(ValueError):
        crime_number(bad)


def test_browser_posts_entered_number():
    checks = """
drawRolePicker({select_role: true, default_crime: 'random'});
assert.equal($('crime-mode').value, 'random');
$('crime-mode').value = 'number'; $('crime-mode').onchange();
assert.equal($('crime-number').hidden, false);
$('crime-number').value = '7'; $('role').value = 'partner';
await $('start-game').onclick();
assert.deepEqual(JSON.parse(requests[0].options.body), {role: 'partner', crime: '7'});
"""
    script = DOM + JS + ENDING_JS + "\n(async () => {" + checks + "})().catch(e => {throw e;});"
    result = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
