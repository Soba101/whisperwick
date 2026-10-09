"""Check 2, action legality: the engine, not the NPC, decides what is possible.

Every bad intent must be rejected with a reason, never raise, and leave the
world exactly as it was. In week 2 these intents come from an LLM, so expect junk.
"""

import pytest
from helpers import fresh_world

from whisperwick.actions import MAX_MESSAGE_CHARS, Intent

# Start positions: Alice at the inn, Bob and Victor at the market,
# Sarah at the temple, Hal at the town hall.
REJECTED = [
    # (description, intent, words expected in the reason)
    ("teleport", {"actor": "npc_alice", "action": "move", "target": "loc_town_hall"}, "not reachable"),
    ("no such place", {"actor": "npc_alice", "action": "move", "target": "loc_moon"}, "unknown location"),
    ("move without target", {"actor": "npc_alice", "action": "move"}, "unknown location"),
    ("no such npc acts", {"actor": "npc_ghost", "action": "look"}, "unknown npc"),
    ("dead mayor acts", {"actor": "npc_mayor", "action": "look"}, "is dead"),
    ("talk to the dead", {"actor": "npc_hal", "action": "talk", "target": "npc_mayor", "message": "hi"}, "is dead"),
    ("no such action", {"actor": "npc_alice", "action": "fly"}, "unknown action"),
    ("talk to absent npc", {"actor": "npc_alice", "action": "talk", "target": "npc_bob", "message": "hi"}, "not here"),
    ("talk to nobody", {"actor": "npc_bob", "action": "talk", "target": "npc_ghost", "message": "hi"}, "unknown npc"),
    ("talk to self", {"actor": "npc_bob", "action": "talk", "target": "npc_bob", "message": "hi"}, "yourself"),
    ("empty message", {"actor": "npc_bob", "action": "talk", "target": "npc_victor", "message": "  "}, "empty"),
    ("huge message", {"actor": "npc_bob", "action": "talk", "target": "npc_victor", "message": "a" * (MAX_MESSAGE_CHARS + 1)}, "longer"),
    ("missing actor", {"action": "look"}, "malformed"),
    ("actor wrong type", {"actor": 7, "action": "look"}, "malformed"),
    ("invented field", {"actor": "npc_bob", "action": "look", "mood": "angry"}, "malformed"),
    ("target wrong type", {"actor": "npc_alice", "action": "move", "target": ["loc_market"]}, "malformed"),
    ("message wrong type", {"actor": "npc_bob", "action": "talk", "target": "npc_victor", "message": 42}, "malformed"),
    ("not even a dict", "steal the sword", "malformed"),
    ("nothing at all", None, "malformed"),
]  # fmt: skip


@pytest.mark.parametrize("name,intent,reason", REJECTED, ids=[r[0] for r in REJECTED])
def test_illegal_intent_is_rejected_and_changes_nothing(name, intent, reason):
    world = fresh_world()
    before = world.state_hash()
    result = world.act(intent)  # must not raise
    assert not result.ok
    assert reason in result.reason
    assert world.state_hash() == before


def test_legal_talk_is_heard_by_everyone_in_the_room():
    world = fresh_world()
    result = world.act(
        {"actor": "npc_bob", "action": "talk", "target": "npc_victor", "message": "Morning."}
    )
    assert result.ok
    assert result.event.data == {"to": "npc_victor", "message": "Morning."}
    assert result.event.witnesses == ["npc_victor"]  # only Victor is at the market with Bob


def test_look_shows_the_room_and_changes_nothing():
    world = fresh_world()
    before = world.state_hash()
    result = world.act({"actor": "npc_bob", "action": "look"})
    assert result.ok
    assert result.observation == {
        "location": "loc_market",
        "people": ["npc_victor"],
        "exits": ["loc_inn", "loc_temple", "loc_town_hall"],
        "bodies": [],
    }
    assert world.state_hash() == before


def test_tampered_intent_object_is_rechecked():
    """An Intent changed after creation must not slip past validation."""
    world = fresh_world()
    before = world.state_hash()
    intent = Intent(actor="npc_bob", action="look")
    intent.actor = ["npc_bob"]  # pydantic does not re-check plain assignment
    broken = Intent.model_construct(actor={}, action="look")  # built with no checks at all
    for bad in (intent, broken):
        result = world.act(bad)
        assert not result.ok and "malformed" in result.reason
    assert world.state_hash() == before


def test_step_survives_junk_in_the_batch():
    """step() is where LLM output arrives in bulk. One bad item must not sink the tick."""
    world = fresh_world()
    results = world.step(
        ["junk", None, 7, {"actor": "npc_bob", "action": "look"}, {"action": "look"}]
    )
    assert len(results) == 5
    assert sum(r.ok for r in results) == 1  # only Bob's look is valid


def test_look_shows_the_body_but_not_as_a_person():
    world = fresh_world()
    result = world.act({"actor": "npc_hal", "action": "look"})
    assert result.observation["people"] == []  # the mayor is dead, so not a person
    assert result.observation["bodies"] == ["npc_mayor"]


def test_mayor_is_never_a_witness():
    world = fresh_world()
    # Hal walks out of the Town Hall. The body must not be listed as seeing it.
    event = world.move("npc_hal", "loc_market").event
    assert "npc_mayor" not in event.witnesses
    assert world.npcs_at("loc_town_hall") == []
    assert world.bodies_at("loc_town_hall") == ["npc_mayor"]
