"""The simulation loop.

Week 1: no LLM. A seeded stub agent picks every action, so the same seed
always gives the same events (replayability).
From week 2, the scheduler will wake LLM agents on interesting events instead.
"""

from whisperwick.stub_agent import intents_for_tick
from whisperwick.world import World


def run(world: World, minutes: int) -> None:
    """Advance the world one tick (game minute) at a time.

    Randomness comes from world.rng, which was seeded when the world was built.
    """
    for _ in range(minutes):
        world.step(intents_for_tick(world))
