"""The command forwards roles and durations without changing measured runs."""

import json

import pytest
from helpers import SCENARIO
from test_play_terminal import fake_setup
from typer.testing import CliRunner

from whisperwick import cli, play_command


@pytest.mark.parametrize("role", ["cousin", "peddler", "partner"])
@pytest.mark.parametrize("scripted", [False, True])
def test_role_reaches_terminal_and_script_runs(monkeypatch, role, scripted):
    calls = []
    monkeypatch.setattr(play_command, "run_with_llm", lambda *args: calls.append(args))
    args = ["play", "--role", role, "--seed", "9", "--days", "3"]
    if scripted:
        args += ["--script", "players/none.yaml"]
    result = CliRunner().invoke(cli.app, args)
    assert result.exit_code == 0, result.output
    sc, _, _, seed, minutes, _, name = calls[0]
    assert sc.role_id == role and sc.private_fact in sc.facts
    assert seed == 9 and minutes == 3 * 1440
    assert name == ("none" if scripted else "terminal")
    assert f"You are {sc.player_title}." in result.output
    assert "What you know:" in result.output


def test_web_default_one_day_and_explicit_days_preserved(monkeypatch):
    calls = []
    monkeypatch.setattr(play_command.web_play, "serve", lambda *a, **kw: calls.append((a, kw)))
    for days, expected in [(None, 1440), (3, 4320)]:
        args = ["play", "--web", "--role", "partner"]
        if days:
            args += ["--days", str(days)]
        result = CliRunner().invoke(cli.app, args)
        assert result.exit_code == 0, result.output
        assert calls[-1][0][4] == expected
        assert calls[-1][1]["role"] == "partner"
        assert calls[-1][0][0].role_id is None  # Each visitor applies their own overlay.


def test_invalid_role_is_a_clear_cli_error():
    result = CliRunner().invoke(cli.app, ["play", "--role", "director"])
    assert result.exit_code == 2 and "unknown role" in result.output


def test_role_metadata_and_private_memory_are_saved(monkeypatch, tmp_path):
    fake_setup(monkeypatch)
    db = tmp_path / "partner.db"
    result = CliRunner().invoke(cli.app, ["play", "--role", "partner", "--seed", "8",
                                         "--scenario", str(SCENARIO), "--db", str(db)],
                                input="quit\n")
    assert result.exit_code == 0, result.output
    data = json.loads(db.with_suffix(".json").read_text())
    assert data["role"] == "partner" and data["seed"] == 8
    assert data["authority"] == ["npc_hal"]
    assert data["player_title"] == "Victor's former business partner"
    assert data["private_fact"] in result.output
    assert any("used to trade cloth" in m for m in data["final_memories"]["npc_victor"])
    assert not any(data["private_fact"] in m for m in data["final_memories"]["npc_bob"])
