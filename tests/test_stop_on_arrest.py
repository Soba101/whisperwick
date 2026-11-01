"""A planned arrest stop keeps the full final minute and normal run outputs."""

import json

import pytest
from helpers import SCENARIO, fresh_world
from test_llm_sim import LookClient
from typer.testing import CliRunner

from whisperwick import cli, llm_cli, llm_run, web_play
from whisperwick.events import EventLog
from whisperwick.llm_sim import run_llm


class ArrestClient(LookClient):
    """Hal walks to Victor, waits until noon, arrests him, then would release him."""

    def __init__(self):
        super().__init__()
        self.hal_turns = 0

    def chat(self, messages, schema):
        if "why" in schema["properties"]:
            return {"suspect": "npc_victor", "why": "The knife."}
        if "thoughts" in schema["properties"]:
            return super().chat(messages, schema)
        if "(npc_alice)" in messages[0]["content"].splitlines()[0]:
            if "recall" in schema["properties"]["action"]["enum"]:
                return {"action": "recall", "message": "Victor"}
        if "(npc_hal)" in messages[0]["content"].splitlines()[0]:
            self.hal_turns += 1
            if self.hal_turns == 1:
                return {"action": "move", "target": "loc_market"}
            if self.hal_turns >= 5:
                action = "arrest" if self.hal_turns == 5 else "release"
                return {"action": action, "target": "npc_victor"}
        return super().chat(messages, schema)


@pytest.mark.parametrize("groups", [False, True])
def test_stops_after_whole_first_arrest_minute(groups):
    full, short, repeat = (fresh_world(2) for _ in range(3))
    turns = []
    _, stats = run_llm(
        short, ArrestClient(), 400, stop_on_arrest=True, group_turns=groups,
        on_turn=lambda w, npc: turns.append((w.clock.tick, npc)),
    )
    run_llm(full, ArrestClient(), 400, group_turns=groups)
    run_llm(repeat, ArrestClient(), 400, stop_on_arrest=True, group_turns=groups)
    events = short.log.all()
    arrest = next(e for e in events if e.type == "arrest")
    assert short.clock.tick == arrest.tick + 1 < full.clock.tick
    assert (arrest.tick, "npc_sarah") in turns  # Sarah's turn follows Hal's this minute.
    assert events == [e for e in full.log.all() if e.tick <= arrest.tick]
    assert events == repeat.log.all()
    assert any(e.type == "release" for e in full.log.all())
    assert short.npcs["npc_victor"].held_by == "npc_hal"
    assert "stopped" not in stats


def test_without_arrest_plays_all_minutes():
    world = fresh_world(2)
    start = world.clock.tick
    run_llm(world, LookClient(), 10, stop_on_arrest=True)
    assert world.clock.tick == start + 10


@pytest.mark.parametrize("enabled", [False, True])
def test_play_saves_normal_outputs_and_actual_minutes(monkeypatch, tmp_path, enabled):
    monkeypatch.setattr(llm_cli, "llm_settings", lambda: ("unused", "fixture"))
    monkeypatch.setattr(llm_cli, "make_client", lambda *args: ArrestClient())
    monkeypatch.setattr(llm_cli.settings, "agent_memory", lambda: True)
    monkeypatch.setattr(llm_cli.settings, "group_turns", lambda: False)
    db = tmp_path / "run.db"
    args = ["play", "--script", "players/none.yaml", "--seed", "2",
            "--scenario", str(SCENARIO), "--db", str(db)]
    if enabled:
        args.append("--stop-on-arrest")
    result = CliRunner().invoke(cli.app, args)
    assert result.exit_code == 0, result.output
    data = json.loads(llm_run.sidecar_path(db).read_text())
    arrest = next(e for e in EventLog.read(str(db)) if e.type == "arrest")
    if enabled:
        assert data["stopped_on"] == "arrest"
        assert data["minutes"] == arrest.tick + 1 - 8 * 60
    else:
        assert "stopped_on" not in data
        assert data["minutes"] == 1440
    assert "stopped" not in data["stats"]
    assert data["interview"] and data["items"] and data["final_memories"]
    assert llm_run.beliefs_path(db).read_text().strip()
    assert llm_run.agent_log_path(db).read_text().strip()
    assert "Interview (who killed" in result.output
    assert "RUN STOPPED EARLY" not in result.output


def test_web_launcher_passes_arrest_option(monkeypatch, tmp_path):
    from whisperwick.scenario import load_scenario

    called = []
    monkeypatch.setattr(web_play, "run_with_llm", lambda *a, **kw: called.append(kw))
    launch = web_play.launcher(
        load_scenario(SCENARIO), SCENARIO, lambda n: str(tmp_path / f"{n}.db"),
        2, 4320, stop_on_arrest=True,
    )
    _, thread = launch()
    thread.join(2)
    assert called[0]["stop_on_arrest"] is True


def test_arrest_minute_keeps_thoughts_and_hour_report():
    world = fresh_world(2)
    world.clock.advance(239)  # One minute before noon, when thoughts and progress are due.
    assert world.act({"actor": "npc_hal", "action": "move", "target": "loc_market"}).ok

    class ArrestNow(LookClient):
        def chat(self, messages, schema):
            if ("action" in schema["properties"]
                    and "(npc_hal)" in messages[0]["content"].splitlines()[0]):
                return {"action": "arrest", "target": "npc_victor"}
            return super().chat(messages, schema)

    hours = []
    client = ArrestNow()
    run_llm(world, client, 10, stop_on_arrest=True,
            on_hour=lambda w, stats: hours.append(w.clock.tick))
    assert world.clock.tick == 720
    assert client.think_calls == 5 and hours == [720]


def test_rejected_arrest_does_not_end_run():
    class AbsentTarget(LookClient):
        def chat(self, messages, schema):
            if ("action" in schema["properties"]
                    and "(npc_hal)" in messages[0]["content"].splitlines()[0]):
                return {"action": "arrest", "target": "npc_victor"}
            return super().chat(messages, schema)

    world = fresh_world(2)
    run_llm(world, AbsentTarget(), 10, stop_on_arrest=True)
    assert world.clock.tick == 8 * 60 + 10
    assert not any(e.type == "arrest" for e in world.log.all())
