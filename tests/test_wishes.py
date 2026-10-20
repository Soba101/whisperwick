"""Unknown actions remain atomic rejections, while sidecar reports count the attempts."""

from helpers import fresh_world
from typer.testing import CliRunner

from whisperwick import cli, llm_run
from whisperwick.llm_agent import act
from whisperwick.llm_client import FakeClient
from whisperwick.wishes import counts


def test_unknown_villager_intents_are_copied_without_changing_events():
    w = fresh_world()
    before = w.state_hash()
    raw = {"actor": "npc_bob", "action": "dance", "message": "by the window"}
    assert not w.act(raw).ok
    raw["message"] = "changed later"
    assert w.wishes == [{"tick": w.clock.tick, "actor": "npc_bob", "action": "dance",
                         "intent": {**raw, "message": "by the window"}}]
    assert w.state_hash() == before and not w.log.all()
    assert not w.act({"actor": "player", "action": "fly"}).ok
    assert len(w.wishes) == 1
    # A model's rejected reply uses the same wish path before the normal retry.
    act(w, "npc_bob", FakeClient([{"action": "lock"}, {"action": "look"}]))
    assert counts(w.wishes) == {"dance": 1, "lock": 1}


def test_cli_prints_sorted_counts_from_sidecar(tmp_path):
    db = tmp_path / "run.db"
    llm_run.write_sidecar(llm_run.sidecar_path(db), {"wishes": [
        {"action": "lock"}, {"action": "dance"}, {"action": "lock"}]})
    result = CliRunner().invoke(cli.app, ["wishes", str(db)])
    assert result.exit_code == 0, result.output
    assert result.output == "dance: 1\nlock: 2\n"
    result = CliRunner().invoke(cli.app, ["wishes", str(tmp_path / "old.db")])
    assert result.exit_code == 0 and result.output == "No wishes.\n"


def test_malformed_unknown_action_keeps_the_raw_json_too():
    w = fresh_world()
    raw = {"actor": "npc_bob", "action": "light_fire", "fuel": ["twigs"]}
    result = w.act(raw)
    assert not result.ok and "malformed" in result.reason
    assert w.wishes[-1]["intent"] == raw and not w.log.all()


def test_run_writes_real_wishes_to_the_sidecar(monkeypatch, tmp_path):
    import json

    from helpers import SCENARIO

    from whisperwick import llm_cli
    from whisperwick.memory import Memories
    from whisperwick.scenario import load_scenario

    monkeypatch.setattr(llm_cli, "llm_settings", lambda: ("unused", "fixture"))
    monkeypatch.setattr(llm_cli, "make_client", lambda *args: FakeClient([]))
    monkeypatch.setattr(llm_cli.run_report, "after_run", lambda *args: {"interview": {}})
    monkeypatch.setattr(llm_cli.run_report, "summary_lines", lambda *args: [])

    def run(world, *args, **kwargs):
        world.act({"actor": "npc_bob", "action": "lock"})
        return Memories(), {}

    monkeypatch.setattr(llm_cli, "run_llm", run)
    db = str(tmp_path / "wishes.db")
    llm_cli.run_with_llm(load_scenario(SCENARIO), SCENARIO, db, None, 1)
    data = json.loads(llm_run.sidecar_path(db).read_text())
    assert counts(data["wishes"]) == {"lock": 1}
    assert data["wishes"][0]["intent"] == {"actor": "npc_bob", "action": "lock"}
