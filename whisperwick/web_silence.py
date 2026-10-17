"""Show only what the engine really did (a look) or that the model failed.

This never invents speech or intent. The event log is not changed.
"""

from whisperwick import story
from whisperwick.world import World


def silence_line(world: World, npc_id: str, errored: bool, tick: int) -> str:
    """A quiet turn in the same shape as the story feed, stamped with the turn's own tick."""
    npc = world.npcs[npc_id]
    place = world.locations[npc.location].name
    words = f"({npc.name} did not answer)" if errored else f"{npc.name} looks around"
    return f"{story.hhmm(tick)}  {place.ljust(story.PLACE_WIDTH)} {words}"
