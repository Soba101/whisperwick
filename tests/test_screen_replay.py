"""A saved fake run must survive the same loop without any model calls."""

import json
import sqlite3

import pytest
from helpers import SCENARIO
from test_parallel_thoughts import RecallingClient

from whisperwick import llm_run
from whisperwick.agent_log import AgentLog, sidecar_part
from whisperwick.belief_log import BeliefLog
from whisperwick.llm_sim import run_llm
from whisperwick.notebook import Notebooks
from whisperwick.scenario import build_world, load_scenario
from whisperwick.screen_replay import check
from whisperwick.screen_turns import pick


@pytest.fixture(name="saved_run")
def source_fixture(tmp_path):
    def save(agent_memory=True):
        db = tmp_path / f"saved-{agent_memory}.db"
        sc = load_scenario(SCENARIO)
        world = build_world(sc, str(db), seed=7)
        beliefs = BeliefLog(llm_run.beliefs_path(db))
        log, books = AgentLog(llm_run.agent_log_path(db)), Notebooks()
        memories, stats = run_llm(
            world, RecallingClient(), 241, evidence=sc.evidence, personalities=sc.personality,
            belief_log=beliefs, notebooks=books, agent_log=log, agent_memory=agent_memory)
        data = llm_run.sidecar_data(SCENARIO, "fixture", 241, stats, sc.secrets, memories)
        data.update(seed=7, **sidecar_part(agent_memory, log, books))
        llm_run.write_sidecar(llm_run.sidecar_path(db), data)
        world.log.db.close()
        return db
    return save


@pytest.mark.parametrize("memory", [True, False])
def test_saved_run_replays(saved_run, memory):
    assert check(saved_run(memory))["ok"]


def test_event_drift_is_reported(saved_run):
    db = saved_run()
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE events SET witnesses = ? WHERE id = 1", ('["npc_missing"]',))
    result = check(db)
    assert not result["ok"] and "events[0]" in result["difference"]
    assert "npc_missing" in result["difference"]


def test_pick_is_seeded_and_samples_both_kinds(saved_run):
    db = saved_run()
    a = pick([db], acts=9, thinks=3, seed=9)
    assert a == pick([db], acts=9, thinks=3, seed=9)
    assert a != pick([db], acts=9, thinks=3, seed=10)
    assert [t["kind"] for t in a["turns"]].count("act") == 9
    assert [t["kind"] for t in a["turns"]].count("think") == 3
    assert json.loads(json.dumps(a)) == a


def test_unused_recalls_are_reported(saved_run):
    db = saved_run()
    with llm_run.agent_log_path(db).open("a") as f:
        f.write(json.dumps(dict(kind="recall", when="act", tick=-1, npc="npc_bob", words="mud")))
        f.write("\n")
    result = check(db)
    assert result["ok"] and result["unused_recalls"] >= 1


def test_group_turn_source_is_refused(saved_run):
    db = saved_run()
    path = llm_run.sidecar_path(db)
    data = json.loads(path.read_text())
    data["group_turns"] = True
    llm_run.write_sidecar(path, data)
    with pytest.raises(ValueError, match="group_turns off"):
        check(db)
