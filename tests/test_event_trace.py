"""trace --event N: what happened, who saw it, and the actor's last thinking before it."""

import json

import pytest
from helpers import SCENARIO
from scene import HAL, belief, cite, new_world, talk
from typer.testing import CliRunner

from whisperwick import cli, event_trace
from whisperwick.belief_log import BeliefLog


def arrest_world():
    """Hal (authority) arrests Victor in the market. Returns the world and the arrest event."""
    world, memories, log = new_world()
    # new_world puts Hal in the market, where Victor already is.
    r = world.act({"actor": "npc_hal", "action": "arrest", "target": "npc_victor"})
    assert r.ok, r.reason
    return world, memories, log, r.event


def explain(world, log, event, names=None):
    return event_trace.explain(world.log.all(), log, event.id, names or {})


def test_arrest_with_cited_memory_and_new_keys():
    world, memories, log, arrest = arrest_world()
    # Hal's thinking came before the arrest, so after_event < arrest id.
    cites = [{"memory_id": "m1", "event_id": 1, "text": "Victor held the knife."}]
    log.add(belief("npc_hal", arrest.id - 1, suspect="npc_victor", because=cites,
                   will_accuse="npc_victor", aim="question Victor", aim_status="new"))  # fmt: skip
    out = explain(world, log, arrest)
    assert f"Event {arrest.id}:" in out and "npc_hal arrests npc_victor" in out
    assert "who: npc_hal" in out and "where: loc_market" in out and "when: day 1" in out
    assert "The world accepted this" in out
    assert "suspect: npc_victor" in out and "will accuse: npc_victor" in out
    assert "aim: question Victor (status: new)" in out
    assert 'm1: "Victor held the knife."' in out
    assert "hunch" not in out


def test_old_record_without_new_keys_and_a_hunch():
    world, _, log, arrest = arrest_world()
    log.add(belief("npc_hal", arrest.id - 1, suspect="npc_victor"))  # no citations
    out = explain(world, log, arrest)
    assert "acted on a hunch (no cited memory)" in out
    assert "will accuse: None" in out and "aim: None (status: None)" in out


def test_no_thinking_before_the_event():
    world, _, log, arrest = arrest_world()
    # A record made at or after the event does not count as "before".
    log.add(belief("npc_hal", arrest.id, suspect="npc_victor"))
    log.add(belief("npc_bob", 0))
    assert "no thinking before this event" in explain(world, log, arrest)


def test_the_newest_record_before_wins():
    world, _, log, arrest = arrest_world()
    log.add(belief("npc_hal", 0, sureness="unsure"))
    log.add(belief("npc_hal", arrest.id - 1, sureness="certain"))
    log.add(belief("npc_hal", arrest.id + 5, sureness="guessing"))
    out = explain(world, log, arrest)
    assert "sureness: certain" in out and "unsure" not in out and "guessing" not in out


def test_talk_shows_claim_and_witnesses():
    world, memories, log = new_world()
    e = talk(world, memories, "npc_victor", "npc_alice", "Hal did it", HAL)
    out = explain(world, log, e, {"npc_hal": "Hal"})
    assert "[claim: accuses Hal]" in out and "Claim: accuses Hal (unverified: " in out
    assert "seen by:" in out


def test_missing_log_and_missing_event():
    world, _, _, arrest = arrest_world()
    assert "No belief log" in explain(world, None, arrest)
    with pytest.raises(ValueError, match="No event 999"):
        event_trace.explain(world.log.all(), None, 999, {})


def save_run(tmp_path):
    db = tmp_path / "run.db"
    world, memories, _ = new_world(db)
    log = BeliefLog(db.with_suffix(".beliefs.jsonl"))
    e1 = talk(world, memories, "player", "npc_bob", "Hal did it", HAL)
    log.add(belief("npc_bob", e1.id - 1, because=[cite(memories, "npc_bob", e1)]))
    e2 = talk(world, memories, "npc_bob", "npc_alice", "Hal did it", HAL)
    world.log.db.close()
    db.with_suffix(".json").write_text(json.dumps({"scenario": str(SCENARIO)}))
    return db, e2


def test_command_explains_an_event_with_names(tmp_path):
    db, e2 = save_run(tmp_path)
    result = CliRunner().invoke(cli.app, ["trace", str(db), "--event", str(e2.id)])
    assert result.exit_code == 0, result.output
    assert "Bob -> Alice" in result.output and "who: Bob" in result.output
    assert "cited memories:" in result.output


def test_command_errors(tmp_path):
    db, _ = save_run(tmp_path)
    run = CliRunner().invoke
    missing = run(cli.app, ["trace", str(db), "--event", "999"])
    assert missing.exit_code == 1 and "No event 999" in missing.output
    both = run(cli.app, ["trace", str(db), "npc_hal", "--event", "1"])
    assert both.exit_code == 1 and "exactly one" in both.output
    neither = run(cli.app, ["trace", str(db)])
    assert neither.exit_code == 1 and "exactly one" in neither.output
