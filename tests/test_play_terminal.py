"""Play mode: the command parser, the terminal player and the play command."""

import json
from pathlib import Path

import pytest
from helpers import fresh_world
from test_play import LookClient, say
from typer.testing import CliRunner

from whisperwick import cli
from whisperwick.llm_sim import run_llm
from whisperwick.player import PLAYER_ID
from whisperwick.player_commands import DEFAULT_WAIT, parse_command
from whisperwick.player_terminal import TerminalPlayer

PLAYERS = Path(__file__).parent.parent / "players"


# ---- the command parser ----

def act(line):
    kind, intent = parse_command(line)
    assert kind == "act"
    return intent


def test_every_command_parses():
    assert parse_command("look") == ("look", None)
    assert parse_command("HELP") == ("help", None)
    assert parse_command("quit") == ("quit", None)
    assert parse_command("wait") == ("wait", DEFAULT_WAIT)
    assert parse_command("wait 3") == ("wait", 3)
    assert act("move loc_inn").target == "loc_inn"
    t = act("talk npc_bob hello  there friend")
    assert (t.action, t.target, t.message) == ("talk", "npc_bob", "hello there friend")
    assert act("take item_knife").item == "item_knife"
    assert act("drop item_knife").action == "drop"
    g = act("give item_knife npc_bob")
    assert (g.item, g.target) == ("item_knife", "npc_bob")
    assert act("show item_knife").target is None
    assert act("show item_knife npc_bob").target == "npc_bob"
    assert act("move loc_inn").actor == PLAYER_ID


@pytest.mark.parametrize("bad", [
    "", "   ", "dance", "move", "move a b", "talk npc_bob", "take", "give item_knife",
    "wait x", "wait 0", "wait -2", "wait 1 2", "look now", "quit now", "show", "show a b c",
])  # fmt: skip
def test_garbage_is_none(bad):
    assert parse_command(bad) is None


# ---- the terminal player ----

def test_terminal_player_with_fake_input():
    w, out = fresh_world(), []
    inputs = iter(["garbage", "look", "talk npc_bob hello", "take item_knife", "wait 2", "quit"])
    player = TerminalPlayer(input_fn=lambda _: next(inputs), output_fn=out.append)
    stats = {}
    run_llm(w, LookClient(), 60, stats=stats, player=player)
    text = "\n".join(out)
    assert "You are at Market (loc_market)" in text
    assert "People here: Bob (npc_bob), Victor (npc_victor)" in text
    assert "I did not understand" in text and "Commands:" in text
    # The reply path: the player sees their own line, and a rejection reason.
    assert "Wren -> Bob: \"hello\"" in text
    assert "You cannot do that" in text  # the knife is in the Town Hall
    # talk (1 min) + take (1 min) + wait 2 = quit at the fourth minute.
    assert w.clock.tick == 8 * 60 + 4
    assert len(stats["player_rejected"]) == 1


def test_terminal_player_shows_npc_replies_and_quits_on_eof():
    w, out = fresh_world(), []
    w.act(say("npc_bob", "x"))  # an event the player is part of
    w.act({"actor": "npc_bob", "action": "talk", "target": PLAYER_ID, "message": "Well met"})

    def eof(_):
        raise EOFError

    player = TerminalPlayer(input_fn=eof, output_fn=out.append)
    assert player.turn(w) is None
    assert 'Bob -> Wren: "Well met"' in "\n".join(out)


# ---- the play command ----

def fake_setup(monkeypatch):
    monkeypatch.setattr(cli.settings, "llm_base_url", lambda: "http://x")
    monkeypatch.setattr(cli.settings, "llm_model", lambda: "m")
    monkeypatch.setattr(cli, "make_client", lambda server, url, model: LookClient())


def test_play_script_smoke(monkeypatch, tmp_path):
    fake_setup(monkeypatch)
    db = tmp_path / "p.db"
    script = PLAYERS / "hide_knife.yaml"
    result = CliRunner().invoke(cli.app, ["play", "--script", str(script), "--db", str(db)])
    assert result.exit_code == 0, result.output
    assert "Player steps rejected: 0" in result.output
    side = json.loads(db.with_suffix(".json").read_text())
    assert side["player"] == "hide_knife" and side["stats"]["player_rejected"] == []


def test_play_terminal_quit_and_bad_script(monkeypatch, tmp_path):
    fake_setup(monkeypatch)
    db = tmp_path / "t.db"
    result = CliRunner().invoke(cli.app, ["play", "--db", str(db)], input="quit\n")
    assert result.exit_code == 0 and "You are at Market" in result.output
    assert '"player": "terminal"' in db.with_suffix(".json").read_text()
    bad = tmp_path / "bad.yaml"
    bad.write_text("steps:\n  - {at: noon, action: look}\n")
    args = ["play", "--script", str(bad), "--db", str(tmp_path / "b.db")]
    result = CliRunner().invoke(cli.app, args)
    assert result.exit_code == 1 and "bad time" in result.output
