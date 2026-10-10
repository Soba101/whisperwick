"""Which memories a villager is shown when it acts. Split out of llm_agent.py (file size)."""

from whisperwick.llm_intent import exits_and_people
from whisperwick.memory import MemoryStream
from whisperwick.world import World


def memory_lines(
    stream: MemoryStream,
    now_tick: int,
    world: World,
    npc_id: str,
    k: int = 8,
    query: str | None = None,
) -> list[str]:
    """The memories most worth showing now. The query is who is here plus where we are.

    A caller may pass its own query (the end-of-run interview asks about the murder).
    """
    if query is None:
        _, people = exits_and_people(world, npc_id)
        here = world.locations[world.npcs[npc_id].location]
        query = " ".join([*(world.npcs[p].name for p in people), here.name])
    # Evidence is always shown, first. In the Gate 1 trial run it decayed out of
    # retrieval after a day, and Victor forgot he was the killer.
    pinned = [m.text for m in stream.memories if m.kind == "evidence"]
    recalled = [
        m for m in stream.retrieve(now_tick, query, k + len(pinned)) if m.kind != "evidence"
    ]
    return pinned + [m.text for m in recalled[:k]]
