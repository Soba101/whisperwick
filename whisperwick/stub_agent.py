"""A scripted stand-in for an LLM agent.

It picks actions with the world's own seeded random generator, so the same
seed always gives the same choices, even across save and load.
The engine checks and the week 1 CLI use it.
Never put a real LLM call here: the checks must stay fast and repeatable.
"""

from whisperwick.actions import Intent
from whisperwick.player import PLAYER_ID
from whisperwick.world import World

# How often each NPC gets a chance to act, in game minutes.
ROUTINE_EVERY = 60
# Chances per check. Whatever is left over means "do nothing this hour".
WANDER_CHANCE = 0.3
CHAT_CHANCE = 0.2

GREETINGS = ["Good morning.", "Busy day?", "Have you seen the mayor?"]


def choose(world: World, npc_id: str) -> Intent | None:
    """Pick one intent for one NPC this tick, or None to do nothing."""
    if world.clock.tick % ROUTINE_EVERY != 0:
        return None
    rng = world.rng
    here = world.npcs[npc_id].location
    roll = rng.random()
    if roll < WANDER_CHANCE:
        # Sort so the choice never depends on list order in the YAML.
        to = rng.choice(sorted(world.locations[here].links))
        return Intent(actor=npc_id, action="move", target=to)
    if roll < WANDER_CHANCE + CHAT_CHANCE:
        others = [n for n in world.npcs_at(here) if n != npc_id]
        if others:
            return Intent(
                actor=npc_id,
                action="talk",
                target=rng.choice(others),
                message=rng.choice(GREETINGS),
            )
    return None


def intents_for_tick(world: World) -> list[Intent]:
    """Every NPC's choice for this tick, in a fixed (sorted) order."""
    # Skip the dead BEFORE choose(): choose() draws from world.rng, and a dead NPC
    # must not use up random numbers, or every living NPC's choices would shift.
    # The player is skipped for the same reason: a human decides for them, not the rng.
    living = (n for n in sorted(world.npcs) if world.npcs[n].alive and n != PLAYER_ID)
    chosen = (choose(world, npc_id) for npc_id in living)
    return [i for i in chosen if i is not None]
