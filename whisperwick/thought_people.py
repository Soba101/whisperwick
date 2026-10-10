"""What a thought reads (memories) and who it may name (people). Split out of thinking.py."""

from whisperwick.memory import Memory, MemoryStream, memory_id

RECENT_MEMORIES = 30  # how many other memories a thought reads, besides all the evidence


def shown_memories(stream: MemoryStream) -> dict[str, Memory]:
    """id -> memory for what a thought reads: all evidence, then the last 30 others.

    Evidence always goes in: it is what this villager knows for certain.
    Earlier thoughts (reflections) are left out, so a belief cannot cite itself.
    """
    indexed = list(enumerate(stream.memories))
    evidence = [(i, m) for i, m in indexed if m.kind == "evidence"]
    recent = [(i, m) for i, m in indexed if m.kind not in ("evidence", "reflection")]
    return {memory_id(i): m for i, m in [*evidence, *recent[-RECENT_MEMORIES:]]}


def people_ids(world, npc_id: str) -> tuple[list[str], list[str]]:
    """(who can be suspected, who can be trusted). The dead are neither.

    A villager may suspect itself (the killer knows). It does not rate its own trust.
    """
    living = sorted(n for n in world.npcs if world.npcs[n].alive)
    return living, [n for n in living if n != npc_id]
