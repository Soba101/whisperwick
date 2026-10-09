"""The belief log: records in order, latest/before lookups, JSON lines on disk."""

import json

from whisperwick.belief_log import BeliefLog


def rec(npc, after_event, suspect=None):
    return {"npc": npc, "after_event": after_event, "suspect": suspect}


def test_latest_is_per_villager_and_none_before_the_first_thought():
    log = BeliefLog()
    assert log.latest("npc_bob") is None
    log.add(rec("npc_bob", 3, "npc_hal"))
    log.add(rec("npc_alice", 4))
    log.add(rec("npc_bob", 9, "npc_victor"))
    assert log.latest("npc_bob")["suspect"] == "npc_victor"
    assert log.latest("npc_alice")["after_event"] == 4


def test_before_gives_what_the_villager_thought_before_an_event():
    log = BeliefLog()
    log.add(rec("npc_bob", 3, "npc_hal"))
    log.add(rec("npc_bob", 9, "npc_victor"))
    assert log.before("npc_bob", 3) is None  # nothing was said before event 3
    assert log.before("npc_bob", 4)["suspect"] == "npc_hal"
    assert log.before("npc_bob", 9)["suspect"] == "npc_hal"  # strictly before
    assert log.before("npc_bob", 10)["suspect"] == "npc_victor"
    assert log.before("npc_alice", 10) is None


def test_records_are_appended_as_json_lines_and_can_be_read_back(tmp_path):
    path = tmp_path / "deep" / "run.beliefs.jsonl"
    log = BeliefLog(path)
    assert not path.exists()  # nothing is written until there is something to write
    log.add(rec("npc_bob", 3, "npc_hal"))
    log.add(rec("npc_alice", 4))
    lines = path.read_text().splitlines()
    assert [json.loads(x)["npc"] for x in lines] == ["npc_bob", "npc_alice"]
    assert BeliefLog.read(path).records == log.records


def test_without_a_path_nothing_touches_the_disk():
    log = BeliefLog()
    log.add(rec("npc_bob", 1))
    assert log.path is None and len(log.records) == 1
