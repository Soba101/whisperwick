"""Trace: who believes it, and the chain behind each belief. No model is called."""

import json

from helpers import SCENARIO
from scene import HAL, belief, cite, new_world, rumour, talk
from typer.testing import CliRunner

from whisperwick import belief_report, cli, trace, trace_command
from whisperwick.belief_log import BeliefLog
from whisperwick.memory import Memories


def texts(steps):
    """Flatten a chain into its lines, in order, so a test can read it like a story."""
    return [x for s in steps for x in [s["text"], *texts(s["then"])]]


def chain_of(result, npc):
    return next(b for b in result["believers"] if b["npc"] == npc)["chain"]


def test_alice_from_bob_from_wren_who_made_it_up():
    world, _, log, e1, e2 = rumour()
    result = trace.trace(world.log.all(), log, "npc_hal")
    assert [b["npc"] for b in result["believers"]] == ["npc_alice", "npc_bob"]
    lines = texts(chain_of(result, "npc_alice"))
    assert lines[0].startswith('npc_bob said: "Hal did it" [claim: npc_hal is the killer]')
    assert f"event {e2.id}" in lines[0]
    # Bob's own belief just before event 2 cites what Wren said, and Wren had no source.
    assert lines[1].startswith('player said: "Hal did it"') and f"event {e1.id}" in lines[1]
    assert lines[2] == "player had no source: made up (the player)"
    assert len(lines) == 3


def test_a_speaker_who_never_suspected_but_had_heard_it():
    # Victor tells Alice. Victor has no belief record, but he heard Bob say it just before.
    world, memories, log, _, e2 = rumour()
    e3 = talk(world, memories, "npc_victor", "npc_alice", "They say Hal did it")
    log.add(belief("npc_alice", e3.id, because=[cite(memories, "npc_alice", e3)]))
    lines = texts(chain_of(trace.trace(world.log.all(), log, "npc_hal"), "npc_alice"))
    assert lines[0].startswith('npc_victor said: "They say Hal did it"')
    assert lines[1].startswith('npc_victor had heard it from npc_bob: "Hal did it"')
    assert f"event {e2.id}" in lines[1]
    assert lines[2].startswith("player said:")  # and so on back to Wren
    assert lines[-1] == "player had no source: made up (the player)"


def test_a_speaker_with_no_source_is_a_guess_or_a_lie():
    world, memories, log = new_world()
    e = talk(world, memories, "npc_victor", "npc_alice", "Hal did it", HAL)
    log.add(belief("npc_alice", e.id, because=[cite(memories, "npc_alice", e)]))
    lines = texts(chain_of(trace.trace(world.log.all(), log, "npc_hal"), "npc_alice"))
    assert lines[-1] == "npc_victor had no source: made up (a guess or a lie)"


def test_first_hand_sight_ends_the_chain():
    # Bob and Victor watch the player walk off. Victor suspects the player because of it.
    world, memories, log = new_world()
    result = world.act({"actor": "player", "action": "move", "target": "loc_temple"})
    memories.observe(result.event, world)
    log.add(
        belief(
            "npc_victor",
            result.event.id,
            "player",
            because=[cite(memories, "npc_victor", result.event)],
        )
    )
    steps = chain_of(trace.trace(world.log.all(), log, "player"), "npc_victor")
    assert len(steps) == 1 and steps[0]["kind"] == "saw" and steps[0]["then"] == []
    assert steps[0]["text"].startswith("saw: ") and "left for loc_temple" in steps[0]["text"]


def test_starting_evidence_and_looks_have_no_event():
    world, memories, log = new_world()
    memories["npc_sarah"].add(480, "I saw Hal hurrying away.", 9, "evidence")
    memories.observe_look("npc_sarah", {"location": "loc_market", "people": ["Hal"]}, 500, world)
    cites = [
        {"memory_id": "m0", "event_id": None, "text": memories["npc_sarah"].memories[0].text},
        {"memory_id": "m1", "event_id": None, "text": memories["npc_sarah"].memories[1].text},
    ]
    log.add(belief("npc_sarah", 0, because=cites))
    lines = texts(chain_of(trace.trace(world.log.all(), log, "npc_hal"), "npc_sarah"))
    assert lines[0] == "remembered from the start: I saw Hal hurrying away."
    assert lines[1].startswith("saw: ") and "you looked around" in lines[1]


def test_someone_speaking_about_themselves():
    world, memories, log = new_world()
    e = talk(world, memories, "npc_hal", "npc_sarah", "Hal did it, you know")
    log.add(belief("npc_sarah", e.id, because=[cite(memories, "npc_sarah", e)]))
    lines = texts(chain_of(trace.trace(world.log.all(), log, "npc_hal"), "npc_sarah"))
    assert lines[-1] == "npc_hal was speaking about themselves"


def test_a_hunch_cites_nothing():
    world, _, log = new_world()
    log.add(belief("npc_bob", 0))
    result = trace.trace(world.log.all(), log, "npc_hal")
    assert result["believers"][0]["hunch"] is True
    assert texts(result["believers"][0]["chain"]) == ["a hunch: no memory cited"]


def test_a_cycle_in_odd_records_stops():
    # Records that point at each other cannot happen in a real run; make sure we still stop.
    world, memories, log = new_world()
    e1 = talk(world, memories, "npc_bob", "npc_alice", "Hal did it", HAL)
    e2 = talk(world, memories, "npc_alice", "npc_bob", "Hal did it", HAL)
    log.add(belief("npc_bob", 1, because=[cite(memories, "npc_bob", e2)]))  # before e2? yes
    log.add(belief("npc_alice", 2, because=[cite(memories, "npc_alice", e1)]))
    # Alice (latest) cites e1 by Bob; Bob's record before e1 does not exist, so use a
    # record Bob made "before e1" that cites e2, and Alice's before e2 that cites e1.
    log.records.clear()
    log.add(belief("npc_bob", 0, because=[cite(memories, "npc_bob", e2)]))
    log.add(belief("npc_alice", 0, because=[cite(memories, "npc_alice", e1)]))
    lines = texts(chain_of(trace.trace(world.log.all(), log, "npc_hal"), "npc_alice"))
    assert lines[-1] == "(already followed above)"
    assert len(lines) <= 6


def test_a_long_relay_stops_at_the_depth_limit():
    world, memories, log = new_world()
    pair = ["npc_bob", "npc_alice"]
    for i in range(9):  # nobody has a belief record: each one had "heard it" from the other
        e = talk(world, memories, pair[i % 2], pair[(i + 1) % 2], f"Hal did it {i}")
    log.add(belief("npc_alice", e.id, because=[cite(memories, "npc_alice", e)]))
    steps = chain_of(trace.trace(world.log.all(), log, "npc_hal"), "npc_alice")
    lines = texts(steps)
    assert lines[-1] == "(stopped: too many steps back)"
    assert len(lines) <= 2 * trace.MAX_DEPTH + 3


def test_used_to_suspect_and_the_order_of_believers():
    world, memories, log = new_world()
    log.add(belief("npc_alice", 0, sureness="unsure"))
    log.add(belief("npc_bob", 0, sureness="certain"))
    log.add(belief("npc_hal", 0, "npc_victor"))
    log.add(belief("npc_sarah", 0, sureness="unsure"))
    log.add(belief("npc_sarah", 0, None))  # Sarah changed her mind
    log.add(belief("npc_victor", 0, sureness="fairly sure"))
    result = trace.trace(world.log.all(), log, "npc_hal")
    assert [b["npc"] for b in result["believers"]] == ["npc_bob", "npc_victor", "npc_alice"]
    assert [b["npc"] for b in result["used_to_suspect"]] == ["npc_sarah"]


def test_trust_in_the_player_is_the_latest_rating_or_not_rated():
    world, _, log = new_world()
    rate = lambda level: [{"person": "player", "level": level, "why": f"{level} why"}]  # noqa: E731
    log.add(belief("npc_bob", 0, trust=rate("high")))
    log.add(belief("npc_bob", 0, trust=rate("low")))
    log.add(belief("npc_alice", 0, trust=[]))
    got = trace.trace(world.log.all(), log, "npc_hal")["trust_in_player"]
    assert got == {"npc_alice": None, "npc_bob": {"level": "low", "why": "low why"}}


def test_own_claims_count_accusations_with_no_source():
    world, _, log, _, _ = rumour()
    own = trace.own_claims(world.log.all(), log)
    # Wren's accusation has no source. Bob's rests on Wren, so it is not his own.
    assert [e.actor for e in own] == ["player"]


# ---- the command ---------------------------------------------------------


def save_run(tmp_path, sidecar=True):
    """A real run file and belief file on disk, as `run` would leave them."""
    db = tmp_path / "run.db"
    world, memories, _ = new_world(db)
    log = BeliefLog(db.with_suffix(".beliefs.jsonl"))
    e1 = talk(world, memories, "player", "npc_bob", "Hal did it", HAL)
    rating = [{"person": "player", "level": "high", "why": "told me straight"}]
    log.add(belief("npc_bob", e1.id, because=[cite(memories, "npc_bob", e1)], trust=rating))
    e2 = talk(world, memories, "npc_bob", "npc_alice", "Hal did it", HAL)
    log.add(belief("npc_alice", e2.id, because=[cite(memories, "npc_alice", e2)]))
    world.log.db.close()
    if sidecar:
        side = {"scenario": str(SCENARIO), "belief_log": str(log.path)}
        db.with_suffix(".json").write_text(json.dumps(side))
    return db


def test_command_prints_the_chain_with_names(tmp_path):
    db = save_run(tmp_path)
    result = CliRunner().invoke(cli.app, ["trace", str(db), "npc_hal"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "Who suspects Hal (npc_hal)?" in out
    assert 'Bob said: "Hal did it" [claim: Hal is the killer]' in out
    assert "Wren had no source: made up (the player)" in out
    assert out.index("Alice:") < out.index("Bob:")  # same sureness, so by id
    assert "Trust in the player:" in out and "Bob: high: told me straight" in out
    assert "Alice: not rated" in out


def test_command_finds_the_log_without_a_sidecar(tmp_path):
    db = save_run(tmp_path, sidecar=False)
    out = CliRunner().invoke(cli.app, ["trace", str(db), "npc_hal"]).output
    assert "Who suspects npc_hal (npc_hal)?" in out and "made up (the player)" in out


def test_command_json_is_the_same_structure(tmp_path):
    db = save_run(tmp_path)
    result = CliRunner().invoke(cli.app, ["trace", str(db), "npc_hal", "--json"])
    data = json.loads(result.output)
    assert data["subject"] == "npc_hal"
    assert [b["npc"] for b in data["believers"]] == ["npc_alice", "npc_bob"]
    assert data["trust_in_player"]["npc_bob"]["level"] == "high"


def test_a_long_thought_is_trimmed_in_the_text(tmp_path):
    b = {"npc": "npc_bob", "name": "Bob", "of_what": None, "sureness": "unsure",
         "thoughts": "x" * 300, "chain": []}  # fmt: skip
    line = trace_command.render_believer(b)[1]
    assert len(line) < 140 and line.endswith('..."')


def test_an_old_run_with_no_belief_log_says_so(tmp_path):
    db = tmp_path / "old.db"
    new_world(db)[0].log.db.close()
    result = CliRunner().invoke(cli.app, ["trace", str(db), "npc_hal"])
    assert result.exit_code == 0 and belief_report.NO_LOG in result.output
    again = CliRunner().invoke(cli.app, ["trace", str(db), "npc_hal", "--json"])
    assert again.exit_code == 0 and json.loads(again.output)["message"] == belief_report.NO_LOG


def test_missing_db_is_an_error(tmp_path):
    result = CliRunner().invoke(cli.app, ["trace", str(tmp_path / "nope.db"), "npc_hal"])
    assert result.exit_code == 1 and "No such file" in result.output


def test_memories_import_is_the_real_class():
    # scene.py builds real Memories; this keeps the helper honest.
    assert isinstance(new_world()[1], Memories)
