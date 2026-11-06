"""Patrol: an authority's one-hour walk through every place. Physics only, never advice.

Start: Hal (the only authority) is in the Town Hall. Bob and Victor are at the market,
Alice at the inn, Sarah at the temple.
"""

from helpers import fresh_world

from whisperwick import belief_text, llm_intent
from whisperwick.patrol import plan_route
from whisperwick.world import World

HAL = {"actor": "npc_hal", "action": "patrol"}


def run_patrol(w):
    """Start Hal's patrol, then tick through the whole hour with no one else acting."""
    assert w.act(HAL).ok
    for _ in range(60):
        w.step([])


def hops(w):
    return [e for e in w.log.all() if e.type == "move" and e.data.get("patrol")]


def test_route_walks_real_links_in_a_fixed_order():
    w = fresh_world()
    route = plan_route(w, "loc_town_hall")
    # Nearest unseen place first, ties by sorted id: market, inn, temple.
    assert route == ["loc_market", "loc_inn", "loc_temple"]
    here = "loc_town_hall"
    for stop in route:
        assert stop in w.locations[here].links  # every hop is a real link
        here = stop


def test_patrol_takes_an_hour_and_logs_one_event_per_stop():
    w = fresh_world()
    start = w.clock.tick
    run_patrol(w)
    assert [e.type for e in w.log.all()] == ["patrol", "move", "move", "move"]
    # Four places, so a quarter of the hour each: the start place, then a hop every 15 minutes.
    assert [e.tick - start for e in hops(w)] == [15, 30, 45]
    assert [e.location for e in hops(w)] == ["loc_market", "loc_inn", "loc_temple"]
    assert w.npcs["npc_hal"].location == "loc_temple"
    assert w.patrols == {}


def test_witnesses_at_each_stop():
    w = fresh_world()
    run_patrol(w)
    start, market, inn, temple = w.log.all()
    assert start.witnesses == []  # the mayor is dead; nobody else is in the Town Hall
    # Moves are seen from both ends, like any move.
    assert market.witnesses == ["npc_bob", "npc_victor", "player"]
    assert "npc_alice" in inn.witnesses  # Alice is at the inn
    assert "npc_sarah" in temple.witnesses  # Sarah is at the temple
    assert "npc_hal" not in inn.witnesses + temple.witnesses


def test_hal_is_busy_until_the_hour_is_up():
    w = fresh_world()
    assert w.act(HAL).ok
    w.step([])
    before = w.state_hash()
    r = w.act({"actor": "npc_hal", "action": "look"})
    assert not r.ok and "on patrol" in r.reason
    assert w.state_hash() == before
    for _ in range(59):
        w.step([])
    assert w.act({"actor": "npc_hal", "action": "look"}).ok


def test_non_authority_cannot_patrol():
    w = fresh_world()
    before = w.state_hash()
    r = w.act({"actor": "npc_bob", "action": "patrol"})
    assert not r.ok and "no authority" in r.reason
    assert w.state_hash() == before


def test_held_authority_cannot_patrol():
    w = fresh_world()
    w.authority.append("npc_bob")  # a second authority, so Bob can hold Hal
    w.npcs["npc_bob"].location = "loc_town_hall"
    assert w.act({"actor": "npc_bob", "action": "arrest", "target": "npc_hal"}).ok
    r = w.act(HAL)
    assert not r.ok and "held" in r.reason


def test_being_held_ends_a_patrol():
    w = fresh_world()
    assert w.act(HAL).ok
    w.npcs["npc_hal"].held_by = "npc_hal"  # held mid-walk (any holder id will do here)
    for _ in range(60):
        w.step([])
    assert w.patrols == {} and hops(w) == []


def test_same_seed_same_events_and_hash():
    a, b = fresh_world(7), fresh_world(7)
    run_patrol(a)
    run_patrol(b)
    assert a.state_hash() == b.state_hash()
    assert [e.model_dump() for e in a.log.all()] == [e.model_dump() for e in b.log.all()]


def test_save_and_load_in_the_middle_finishes_the_same_walk():
    whole, cut = fresh_world(), fresh_world()
    run_patrol(whole)
    assert cut.act(HAL).ok
    for _ in range(20):
        cut.step([])
    resumed = World.from_dict(cut.to_dict())
    for _ in range(40):
        resumed.step([])
    assert resumed.state_hash() == whole.state_hash()


def test_patrol_is_listed_for_authority_only_and_plainly():
    w = fresh_world()
    assert "patrol" in llm_intent.actions_for(w, "npc_hal")
    assert "patrol" not in llm_intent.actions_for(w, "npc_bob")
    text = " ".join(belief_text.custody_lines(w, "npc_hal"))
    assert "patrol: walk through every place in turn for one hour" in text
    assert "patrol" not in " ".join(belief_text.custody_lines(w, "npc_bob"))
