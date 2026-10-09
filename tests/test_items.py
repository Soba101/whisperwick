"""Items: take, drop, give and show are strict, logged, and never lose an item.

Start: the knife lies in the Town Hall (Hal and the dead mayor are there).
Victor holds his boots at the market, with Bob.
"""

import json

import pytest
from helpers import fresh_world, run_ticks

from whisperwick.actions import Intent
from whisperwick.items import Item
from whisperwick.world import NPC, World


def intent(actor, action, **kw):
    return {"actor": actor, "action": action, **kw}


def test_take_moves_item_to_actor():
    w = fresh_world()
    r = w.act(intent("npc_hal", "take", item="item_knife"))
    assert r.ok
    assert w.items["item_knife"].holder == "npc_hal"
    assert w.items["item_knife"].location is None
    assert w.items_held("npc_hal") == ["item_knife"]
    assert w.items_at("loc_town_hall") == []


def test_drop_puts_item_where_actor_stands():
    w = fresh_world()
    assert w.move("npc_victor", "loc_inn").ok
    assert w.act(intent("npc_victor", "drop", item="item_boots")).ok
    assert w.items["item_boots"].location == "loc_inn"
    assert w.items["item_boots"].holder is None


def test_give_changes_holder():
    w = fresh_world()
    r = w.act(intent("npc_victor", "give", item="item_boots", target="npc_bob"))
    assert r.ok
    assert w.items["item_boots"].holder == "npc_bob"


def test_show_moves_nothing():
    w = fresh_world()
    before = w.items["item_boots"].model_dump()
    assert w.act(intent("npc_victor", "show", item="item_boots", target="npc_bob")).ok
    assert w.items["item_boots"].model_dump() == before


def test_show_to_the_room_needs_no_target():
    w = fresh_world()
    r = w.act(intent("npc_victor", "show", item="item_boots"))
    assert r.ok
    assert "to" not in r.event.data


def test_events_have_witnesses_and_item_details():
    w = fresh_world()
    r = w.act(intent("npc_victor", "give", item="item_boots", target="npc_bob"))
    e = r.event
    assert e.type == "give" and e.actor == "npc_victor" and e.location == "loc_market"
    assert e.witnesses == ["npc_bob", "player"]  # living people here, never the actor
    assert e.data["item"] == "item_boots" and e.data["to"] == "npc_bob"
    assert e.data["item_name"] == "muddy boots"
    assert "caked" in e.data["item_description"]
    # Hal takes the knife; the dead mayor is in the room but does not witness.
    take = w.act(intent("npc_hal", "take", item="item_knife")).event
    assert take.witnesses == [] and "to" not in take.data


REJECTED = [
    ("take unknown", intent("npc_hal", "take", item="item_nope"), "unknown item"),
    ("take without item", intent("npc_hal", "take"), "unknown item"),
    ("take elsewhere", intent("npc_bob", "take", item="item_knife"), "not here"),
    ("take held item", intent("npc_bob", "take", item="item_boots"), "not here"),
    ("drop unknown", intent("npc_victor", "drop", item="item_nope"), "unknown item"),
    ("drop not held", intent("npc_hal", "drop", item="item_boots"), "not holding"),
    ("drop ground item", intent("npc_hal", "drop", item="item_knife"), "not holding"),
    (
        "give not held",
        intent("npc_bob", "give", item="item_boots", target="npc_victor"),
        "not holding",
    ),
    (
        "give unknown npc",
        intent("npc_victor", "give", item="item_boots", target="npc_x"),
        "unknown npc",
    ),
    ("give no target", intent("npc_victor", "give", item="item_boots"), "unknown npc"),
    (
        "give absent",
        intent("npc_victor", "give", item="item_boots", target="npc_alice"),
        "not here",
    ),
    ("give self", intent("npc_victor", "give", item="item_boots", target="npc_victor"), "yourself"),
    ("show not held", intent("npc_bob", "show", item="item_boots"), "not holding"),
    (
        "show to absent",
        intent("npc_victor", "show", item="item_boots", target="npc_alice"),
        "not here",
    ),
    (
        "show to self",
        intent("npc_victor", "show", item="item_boots", target="npc_victor"),
        "yourself",
    ),
    ("item wrong type", intent("npc_hal", "take", item=5), "malformed"),
]


@pytest.mark.parametrize("name,bad,words", REJECTED, ids=[r[0] for r in REJECTED])
def test_bad_item_intents_are_rejected_and_change_nothing(name, bad, words):
    w = fresh_world()
    before = w.state_hash()
    r = w.act(bad)
    assert not r.ok and words in r.reason
    assert w.state_hash() == before


def test_cannot_give_to_the_dead():
    w = fresh_world()
    w.npcs["npc_hal"].alive = False  # kill a living neighbour of the knife
    w.npcs["npc_victor"].location = "loc_town_hall"
    before = w.state_hash()
    r = w.act(intent("npc_victor", "give", item="item_boots", target="npc_hal"))
    assert not r.ok and "is dead" in r.reason
    assert w.state_hash() == before


def test_look_lists_ground_items_and_own_holdings():
    w = fresh_world()
    hall = w.act(intent("npc_hal", "look")).observation
    assert hall["items"] == ["item_knife"] and hall["holding"] == []
    market = w.act(intent("npc_bob", "look")).observation
    # Victor's boots are held, so Bob cannot see them.
    assert market["items"] == [] and market["holding"] == []
    assert w.act(intent("npc_victor", "look")).observation["holding"] == ["item_boots"]


def test_save_load_round_trip_keeps_items():
    w = fresh_world()
    w.act(intent("npc_hal", "take", item="item_knife"))
    loaded = World.from_dict(json.loads(json.dumps(w.to_dict())))
    assert loaded.items_held("npc_hal") == ["item_knife"]
    assert loaded.state_hash() == w.state_hash()


def test_items_are_part_of_the_state_hash():
    w = fresh_world()
    before = w.state_hash()
    w.act(intent("npc_hal", "take", item="item_knife"))
    assert w.state_hash() != before


def test_determinism_with_item_actions():
    def run():
        w = fresh_world(seed=3)
        w.step([Intent(actor="npc_hal", action="take", item="item_knife")])
        return run_ticks(w, 60)

    assert run() == run()


def make(items):
    from whisperwick.clock import Clock
    from whisperwick.events import EventLog
    from whisperwick.world import Location

    locs = [Location(id="loc_a", name="A", links=[])]
    npcs = [NPC(id="npc_a", name="A", occupation="x", location="loc_a")]
    npcs.append(NPC(id="npc_d", name="D", occupation="x", location="loc_a", alive=False))
    return World(locs, npcs, Clock(), EventLog(), items=items)


BAD_SETUPS = [
    ("duplicate", [Item(id="i", name="n", description="d", location="loc_a")] * 2, "duplicate"),
    ("neither", [Item(id="i", name="n", description="d")], "exactly one"),
    (
        "both",
        [Item(id="i", name="n", description="d", location="loc_a", holder="npc_a")],
        "exactly one",
    ),
    (
        "bad location",
        [Item(id="i", name="n", description="d", location="loc_x")],
        "unknown location",
    ),
    ("bad holder", [Item(id="i", name="n", description="d", holder="npc_x")], "unknown npc"),
    ("dead holder", [Item(id="i", name="n", description="d", holder="npc_d")], "dead"),
]


@pytest.mark.parametrize("name,items,words", BAD_SETUPS, ids=[b[0] for b in BAD_SETUPS])
def test_broken_item_setup_is_refused(name, items, words):
    with pytest.raises(ValueError, match=words):
        make(items)
