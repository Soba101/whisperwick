"""World setup checks: a broken scenario or reused log fails loudly at the start.

These raise on purpose. Bad scenario data is our bug, not agent input,
and crashing mid-run (hours into an experiment) would be far worse.
"""

import pytest
from helpers import SCENARIO

from whisperwick.clock import Clock
from whisperwick.events import Event, EventLog
from whisperwick.scenario import build_world, load_scenario
from whisperwick.world import NPC, Location, World

INN = Location(id="loc_inn", name="Inn", links=[])
ALICE = NPC(id="npc_alice", name="Alice", occupation="innkeeper", location="loc_inn")


def build(locations, npcs):
    return World(locations, npcs, Clock(), EventLog())


def test_npc_in_unknown_place_is_refused():
    lost = ALICE.model_copy(update={"location": "loc_nowhere"})
    with pytest.raises(ValueError, match="unknown location"):
        build([INN], [lost])


def test_dead_link_is_refused():
    broken = INN.model_copy(update={"links": ["loc_moon"]})
    with pytest.raises(ValueError, match="unknown location"):
        build([broken], [ALICE])


def test_duplicate_ids_are_refused():
    with pytest.raises(ValueError, match="duplicate npc"):
        build([INN], [ALICE, ALICE])
    with pytest.raises(ValueError, match="duplicate location"):
        build([INN, INN], [ALICE])


def test_log_file_with_old_events_is_refused(tmp_path):
    """Two runs in one database would mix their histories."""
    db = str(tmp_path / "run.db")
    EventLog(db).append(Event(tick=0, type="move", actor="npc_alice", location="loc_inn"))
    with pytest.raises(ValueError, match="already has events"):
        EventLog(db)


def scenario_with(**changes):
    """The real scenario with some fields swapped, to test the validation."""
    return load_scenario(SCENARIO).model_copy(update=changes)


def test_secret_naming_unknown_npc_or_place_is_refused():
    with pytest.raises(ValueError, match="unknown npc npc_victer"):
        build_world(scenario_with(secrets={"murderer": "npc_victer"}))
    with pytest.raises(ValueError, match="unknown location loc_moon"):
        build_world(scenario_with(secrets={"scene": "loc_moon"}))
    # Other values (plain words, numbers) are not ids, so they are left alone.
    build_world(scenario_with(secrets={"weapon": "knife", "count": 3}))


def test_evidence_for_unknown_npc_is_refused():
    with pytest.raises(ValueError, match="unknown npc npc_ghost"):
        build_world(scenario_with(evidence={"npc_ghost": ["boo"]}))


def test_real_scenario_has_a_dead_mayor_and_evidence():
    scenario = load_scenario(SCENARIO)
    world = build_world(scenario)
    assert world.npcs["npc_mayor"].alive is False
    living = sorted(n.id for n in scenario.npcs if n.alive)
    assert sorted(scenario.evidence) == living  # everyone alive has a private memory
