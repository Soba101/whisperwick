"""World engine tests: legal moves, illegal moves, witnesses, replays."""

from pathlib import Path

from whisperwick.scenario import build_world, load_scenario
from whisperwick.sim import run

SCENARIO = Path(__file__).parent.parent / "scenarios" / "murder_of_the_mayor.yaml"


def fresh_world():
    return build_world(load_scenario(SCENARIO))


def test_move_to_neighbour_works_and_is_logged():
    world = fresh_world()
    result = world.move("npc_alice", "loc_market")  # inn -> market is linked
    assert result.ok
    assert world.npcs["npc_alice"].location == "loc_market"
    assert world.log.all()[0].data == {"from": "loc_inn", "to": "loc_market"}


def test_no_teleporting():
    world = fresh_world()
    result = world.move("npc_alice", "loc_town_hall")  # inn -> town hall is NOT linked
    assert not result.ok
    assert world.npcs["npc_alice"].location == "loc_inn"  # nothing changed
    assert world.log.all() == []  # and nothing was logged


def test_witnesses_are_people_at_either_end():
    world = fresh_world()
    # Bob and Victor start at the market. Alice walks in from the inn.
    event = world.move("npc_alice", "loc_market").event
    assert event.witnesses == ["npc_bob", "npc_victor", "player"]


def test_same_seed_same_events():
    """Week 1 exit check: a seeded run replays identically."""
    a, b = fresh_world(), fresh_world()
    run(a, minutes=24 * 60)
    run(b, minutes=24 * 60)
    assert a.log.all() == b.log.all()
    assert len(a.log.all()) > 0  # make sure the test is not trivially passing


def test_stub_never_picks_the_dead_mayor():
    # The unchanged golden snapshot events prove the rng stream was not disturbed.
    from whisperwick.stub_agent import intents_for_tick

    world = fresh_world()
    for _ in range(300):
        intents = intents_for_tick(world)
        for intent in intents:
            assert intent.actor != "npc_mayor" and intent.target != "npc_mayor"
        world.step(intents)
