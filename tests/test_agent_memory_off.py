"""With villager memory off, prompts and schemas are exactly the week 5 ones."""

import pytest
from helpers import SCENARIO, fresh_world
from test_recall import thought

from whisperwick import cli, llm_agent, llm_run, settings, thinking
from whisperwick.agent_log import AgentLog, sidecar_part
from whisperwick.belief_log import BeliefLog
from whisperwick.llm_sim import run_llm
from whisperwick.notebook import Notebooks
from whisperwick.scenario import build_world, load_scenario
from whisperwick.thinking import prepare


def test_intent_schema_and_prompt_have_no_recall_by_default():
    world = fresh_world()
    schema = llm_agent.intent_schema(world, "npc_bob")
    assert "recall" not in schema["properties"]["action"]["enum"]
    assert schema["properties"]["action"]["enum"] == [
        "move", "talk", "look", "take", "drop", "give", "show",
    ]  # fmt: skip
    text = llm_agent.build_messages(world, "npc_bob")[0]["content"]
    assert "recall" not in text and "notebook" not in text


def test_thought_schema_and_ask_are_the_old_ones_by_default():
    sch = thinking.schema(fresh_world(), "npc_bob", ["m0"])
    assert list(sch["properties"]) == [
        "thoughts", "suspect", "of_what", "sureness", "will_accuse", "aim", "aim_status",
        "because", "trust",
    ]  # fmt: skip
    assert sch["required"] == list(sch["properties"])
    s = thinking.MemoryStream()
    s.add(1, "I saw Victor.", 5)
    p = prepare(s, "npc_bob", fresh_world(), None, BeliefLog())
    assert not p.memory and list(p.schema["properties"]) == list(sch["properties"])
    text = " ".join(m["content"] for m in p.messages)
    assert "notebook" not in text and "searched" not in text


def test_a_whole_run_with_memory_off_never_mentions_recall_or_notebook():
    world = build_world(load_scenario(SCENARIO), ":memory:", seed=3)

    class Spy:
        def __init__(self):
            self.seen = []

        def chat(self, messages, schema):
            self.seen.append(repr(messages) + repr(schema))
            if "thoughts" in schema["properties"]:
                return thought(because=[], suspect=None)
            return {"action": "look"}

    spy, nb, log = Spy(), Notebooks(), AgentLog()
    run_llm(world, spy, 4 * 60 + 5, agent_memory=False, notebooks=nb, agent_log=log)
    assert spy.seen and not any("recall" in t or "notebook" in t for t in spy.seen)
    assert nb.to_dict() == {} and log.records == []


def test_memory_setting_defaults_on_and_rejects_bad_values(tmp_path, monkeypatch):
    monkeypatch.delenv("WHISPERWICK_MEMORY", raising=False)
    env = tmp_path / ".env"
    assert settings.agent_memory(env) is True
    env.write_text("WHISPERWICK_MEMORY=off\n")
    assert settings.agent_memory(env) is False
    env.write_text("WHISPERWICK_MEMORY=maybe\n")
    with pytest.raises(ValueError, match="WHISPERWICK_MEMORY"):
        settings.agent_memory(env)


def test_cli_exits_on_a_bad_memory_setting(monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setattr(cli.settings, "llm_base_url", lambda: "http://x")
    monkeypatch.setattr(cli.settings, "llm_model", lambda: "m")
    monkeypatch.setattr(cli.settings, "parallel", lambda: 1)
    monkeypatch.setattr(cli.settings, "llm_server", lambda: "ollama")

    def bad():
        raise ValueError("WHISPERWICK_MEMORY must be on or off")

    monkeypatch.setattr(cli.settings, "agent_memory", bad)
    db = tmp_path / "x.db"
    res = CliRunner().invoke(cli.app, ["run", "--agent", "llm", "--db", str(db)])
    assert res.exit_code == 1 and "WHISPERWICK_MEMORY" in res.output


def test_sidecar_part_and_agent_log_file(tmp_path):
    path = llm_run.agent_log_path(tmp_path / "run.db")
    assert path.name == "run.agent.jsonl"
    log, nb = AgentLog(path), Notebooks()
    log.recall(5, "npc_bob", "act", "knife", ["m1"])
    log.recall(9, "npc_bob", "think", "well", [])
    nb.apply("npc_bob", {"notebook_me": "hi"}, [])
    assert len(path.read_text().splitlines()) == 2
    assert sidecar_part(True, log, nb) == {
        "agent_memory": True, "recalls": {"act": 1, "think": 1},
        "notebooks": {"npc_bob": {"me": "hi", "people": {}}},
    }  # fmt: skip
    assert sidecar_part(False, log, nb) == {"agent_memory": False}
