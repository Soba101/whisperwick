"""The simulation loop.

Week 1: no LLM. NPCs wander on a fixed, seeded routine so we can prove
that the same seed always gives the same events (replayability).
From week 2, the scheduler will wake LLM agents on interesting events instead.
"""

import random

from whisperwick.world import World

# How often each NPC gets a chance to act, in game minutes.
ROUTINE_EVERY = 60
# Chance an NPC wanders to a neighbouring place on each check.
WANDER_CHANCE = 0.3


def run(world: World, minutes: int, seed: int) -> None:
    """Advance the world minute by minute for the given number of game minutes."""
    # One seeded random generator for the whole run = deterministic replays.
    rng = random.Random(seed)
    for _ in range(minutes):
        if world.clock.tick % ROUTINE_EVERY == 0:
            # Sort NPC ids so the order never depends on dict internals.
            for npc_id in sorted(world.npcs):
                if rng.random() < WANDER_CHANCE:
                    here = world.npcs[npc_id].location
                    # Sort neighbours too, for the same reason.
                    to = rng.choice(sorted(world.locations[here].links))
                    world.move(npc_id, to)
        world.clock.advance()
