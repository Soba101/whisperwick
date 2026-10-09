"""World setup checks: a broken scenario or reused log fails loudly at the start.

These raise on purpose. Bad scenario data is our bug, not agent input,
and crashing mid-run (hours into an experiment) would be far worse.
"""

import pytest

from whisperwick.clock import Clock
from whisperwick.events import Event, EventLog
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
