"""Check 3, invariants: the world never enters an impossible state.

Checked after every single tick of the determinism runs, so a bad state
is caught at the tick where it first appears.
"""

import pytest
from helpers import SEEDS, TICKS, fresh_world, run_ticks

from whisperwick.world import World


def check_invariants(world: World, last_tick: list[int]) -> None:
    # Time only moves forward, one minute per tick.
    assert world.clock.tick == last_tick[0] + 1, "clock skipped or went backwards"
    last_tick[0] = world.clock.tick

    # Every path leads somewhere that exists.
    for loc in world.locations.values():
        assert all(link in world.locations for link in loc.links), f"{loc.id}: dead link"

    # Every NPC stands somewhere that exists.
    for npc in world.npcs.values():
        assert npc.location in world.locations, f"{npc.id} is in unknown place {npc.location}"

    events = world.log.all()
    for e in events:
        # Every reference in the log points to something real.
        assert e.actor in world.npcs, f"event {e.id}: unknown actor {e.actor}"
        assert e.location in world.locations, f"event {e.id}: unknown location {e.location}"
        assert all(w in world.npcs for w in e.witnesses), f"event {e.id}: unknown witness"
        # Nobody "witnesses" their own action; that is memory, not perception.
        assert e.actor not in e.witnesses, f"event {e.id}: actor listed as own witness"
        # No event is dated in the future.
        assert e.tick < world.clock.tick, f"event {e.id} is from the future"
        if e.type == "talk":
            assert e.data["to"] in e.witnesses, f"event {e.id}: listener did not hear it"

    # Event ids run 1, 2, 3, ... with no gaps: the log is append-only.
    assert [e.id for e in events] == list(range(1, len(events) + 1))


@pytest.mark.parametrize("seed", SEEDS)
def test_invariants_hold_every_tick(seed):
    world = fresh_world(seed)
    last_tick = [world.clock.tick]  # a list so the callback can update it
    run_ticks(world, TICKS, after_tick=lambda w: check_invariants(w, last_tick))
