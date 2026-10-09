"""End-of-run interview: ask each villager who they think killed the mayor.

Strictly read-only. It never calls world.act, never adds memories and never writes
events, so asking cannot change the story it measures. The answers are saved in the
sidecar file only. A stand-in for real beliefs until week 4.
"""

from whisperwick import llm_agent
from whisperwick.llm_client import LLMError
from whisperwick.memory import Memories, MemoryStream
from whisperwick.world import World

QUESTION = (
    "Who do you think killed Mayor Aldric? Give the id of your main suspect, "
    "or null if you truly have no idea, and one sentence why."
)
# Words that pull murder-related memories to the top of retrieval.
MEMORY_QUERY = "Mayor Aldric murder killed stabbed knife blood suspect body"
MAX_WHY_CHARS = 300


def schema(world: World) -> dict:
    """The suspect can only be a living person (the asker and the player included)."""
    living = sorted(n for n in world.npcs if world.npcs[n].alive)
    return {
        "type": "object",
        "properties": {
            "suspect": {"enum": [*living, None]},
            "why": {"type": "string", "maxLength": MAX_WHY_CHARS},
        },
        "required": ["suspect", "why"],
        "additionalProperties": False,
    }


def messages(world: World, npc_id: str, stream: MemoryStream) -> list[dict]:
    """A short in-character system message plus the question."""
    me = world.npcs[npc_id]
    lines = [
        f"You are {me.name} ({me.id}), the village {me.occupation}. Stay in character.",
        "Reply only with JSON. Use exact ids, never names.",
        "Only say what you saw or were told. Never invent objects, records or events.",
        "Living people: " + ", ".join(f"{n} ({world.npcs[n].name})" for n in sorted(world.npcs)
                                      if world.npcs[n].alive),
    ]  # fmt: skip
    # k=12, more than a normal turn's 8: the answer should rest on the whole run,
    # not only on the last few hours.
    mem = llm_agent.memory_lines(
        stream, world.clock.tick, world, npc_id, k=12, query=MEMORY_QUERY
    )
    if mem:
        lines += ["You remember:", *(f"- {m}" for m in mem)]
    return [
        {"role": "system", "content": "\n".join(lines)},
        {"role": "user", "content": QUESTION},
    ]


def interview(
    world: World, memories: Memories, client, npc_ids: list[str], stats: dict | None = None
) -> dict[str, dict]:
    """One model call per living NPC, in sorted order. Errors are counted, never raised."""
    out = {}
    for npc_id in sorted(npc_ids):
        if not world.npcs[npc_id].alive:
            continue
        # `in` check first: reading Memories[x] for a missing key would create a stream.
        stream = memories[npc_id] if npc_id in memories else MemoryStream()
        try:
            reply = client.chat(messages(world, npc_id, stream), schema(world))
            suspect, why = reply["suspect"], str(reply["why"])
            if suspect is not None and suspect not in world.npcs:
                raise ValueError(f"unknown suspect {suspect}")
            out[npc_id] = {"suspect": suspect, "why": why}
        except (LLMError, KeyError, TypeError, ValueError) as e:
            if stats is not None:
                stats["interview_errors"] = stats.get("interview_errors", 0) + 1
            out[npc_id] = {"suspect": None, "why": f"error: {e}"}
    return out
