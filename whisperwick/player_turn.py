"""One minute of player input for the run loop.

The player's intents go through World.act like any NPC's. A good one is logged,
remembered and wakes the villagers who saw it. A bad one is NOT fatal: the player
gets the reason and the run goes on.
"""

from whisperwick.memory import Memories
from whisperwick.player import PlayerSource
from whisperwick.scheduler import Scheduler
from whisperwick.world import World


def apply_player_turn(
    world: World,
    player: PlayerSource,
    memories: Memories,
    scheduler: Scheduler,
    stats: dict,
) -> bool:
    """Apply the player's intents for this minute. Returns False when the player quits."""
    intents = player.turn(world)
    if intents is None:
        return False
    for intent in intents:
        result = world.act(intent)
        if result.event:
            # Same as an NPC event: remember it right away and wake the witnesses.
            memories.observe(result.event, world)
            scheduler.notice(result.event)
        if not result.ok:
            # Kept in the stats so a run can be checked afterwards.
            stats.setdefault("player_rejected", []).append(
                {
                    "tick": world.clock.tick,
                    "intent": intent.model_dump(exclude_none=True),
                    "reason": result.reason,
                }
            )
        player.report(intent, result)
    return True
