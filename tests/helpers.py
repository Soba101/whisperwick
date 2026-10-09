"""Shared helpers for the engine checks. See VERIFY.md for what each check proves."""

from collections.abc import Callable
from pathlib import Path

from whisperwick.scenario import build_world, load_scenario
from whisperwick.stub_agent import intents_for_tick
from whisperwick.world import World

SCENARIO = Path(__file__).parent.parent / "scenarios" / "murder_of_the_mayor.yaml"

# Seeds and length used by the determinism and invariant checks.
SEEDS = [1, 42, 1234]
TICKS = 300  # five game hours: enough for every NPC to move and talk


def fresh_world(seed: int = 42) -> World:
    return build_world(load_scenario(SCENARIO), seed=seed)


def run_ticks(
    world: World, ticks: int, after_tick: Callable[[World], None] | None = None
) -> list[str]:
    """Drive the world with the scripted stub agent. Returns the state hash after each tick."""
    hashes = []
    for _ in range(ticks):
        world.step(intents_for_tick(world))
        if after_tick:
            after_tick(world)
        hashes.append(world.state_hash())
    return hashes
