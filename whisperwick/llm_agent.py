"""An NPC that is driven by a language model.

The model only proposes an Intent. The engine (World.act) still decides
what really happens. We never trust the model's output without that check.
"""

from collections.abc import Sequence

from pydantic import ValidationError

from whisperwick.actions import MAX_MESSAGE_CHARS, ActionResult, Intent
from whisperwick.llm_client import LLMError
from whisperwick.memory import MemoryStream
from whisperwick.world import World

ACTIONS = ["move", "talk", "look", "take", "drop", "give", "show"]


def exits_and_people(world: World, npc_id: str) -> tuple[list[str], list[str]]:
    """Exit location ids from here, and ids of the other NPCs here. Both sorted."""
    here = world.npcs[npc_id].location
    exits = sorted(world.locations[here].links)
    people = [n for n in world.npcs_at(here) if n != npc_id]
    return exits, people


def usable_items(world: World, npc_id: str) -> list[str]:
    """Ids of items on the ground here plus items this NPC holds. Sorted, no repeats."""
    here = world.npcs[npc_id].location
    return sorted({*world.items_at(here), *world.items_held(npc_id)})


def item_lines(world: World, ids: list[str]) -> str:
    """'id (name: description)' for each item, or 'nothing'."""
    return (", ".join(f"{i} ({world.items[i].name}: {world.items[i].description})" for i in ids)
            or "nothing")  # fmt: skip


def intent_schema(world: World, npc_id: str) -> dict:
    """JSON schema for this one turn.

    Target can only be a real exit or a person here, so the model cannot
    write a display name like "Victor" in place of "npc_victor".
    Item can only be an item lying here or one this NPC holds, so no invented objects.
    """
    exits, people = exits_and_people(world, npc_id)
    return {
        "type": "object",
        "properties": {
            "action": {"enum": ACTIONS},
            "target": {"enum": [*exits, *people, None]},
            "item": {"enum": [*usable_items(world, npc_id), None]},
            "message": {"type": ["string", "null"], "maxLength": MAX_MESSAGE_CHARS},
        },
        "required": ["action", "target", "item", "message"],
        "additionalProperties": False,
    }


def build_messages(
    world: World, npc_id: str, memories: Sequence[str] = (), feedback: str | None = None
) -> list[dict]:
    """One compact system message: who I am, where I am, who and what is around."""
    me = world.npcs[npc_id]
    exits, people = exits_and_people(world, npc_id)
    here = world.locations[me.location]
    lines = [
        f"You are {me.name} ({me.id}), the village {me.occupation}.",
        "Reply only with JSON. Use exact ids, never names.",
        # The trial run invented ledgers, letters and gold. Facts belong to the engine.
        "Only claim things you saw or were told. Never invent objects, records or events.",
        # Spell out what each action needs. The schema alone cannot say
        # "move takes an exit, talk takes a person".
        "Actions: move (target = an exit id), talk (target = a person id, plus a message),"
        " look (target = null),"
        " take/drop (item = an item id), give (item + target = a person id),"
        " show (item, target = a person id, or null for everyone here).",
        f"Time: {world.clock.label()}.",
        f"You are at {here.id} ({here.name}).",
        "Exits: " + ", ".join(f"{e} ({world.locations[e].name})" for e in exits),
        "People here: "
        + (", ".join(f"{p} ({world.npcs[p].name}, {world.npcs[p].occupation})" for p in people)
           or "nobody"),
        "Items on the ground here: " + item_lines(world, world.items_at(here.id)),
        "You carry: " + item_lines(world, world.items_held(npc_id)),
    ]  # fmt: skip
    # A body is not a person you can talk to, but you can see it. Say so plainly.
    bodies = world.bodies_at(here.id)
    if bodies:
        lines.append("Lying dead here: " + ", ".join(f"{b} ({world.npcs[b].name})" for b in bodies))
    if memories:
        lines.append("You remember:")
        lines += [f"- {m}" for m in memories]
    if feedback:
        # The engine's own words, so the model can fix its mistake.
        lines.append(f"Your last action was rejected: {feedback}. Choose again.")
    # A short user turn as well: chat models answer more reliably
    # when there is a question to reply to, not only a system message.
    return [
        {"role": "system", "content": "\n".join(lines)},
        {"role": "user", "content": "What do you do now?"},
    ]


def memory_lines(
    stream: MemoryStream, now_tick: int, world: World, npc_id: str, k: int = 8,
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


def decide(
    world: World,
    npc_id: str,
    client,
    memories: Sequence[str] = (),
    feedback: str | None = None,
    stats: dict | None = None,
) -> Intent:
    """Ask the model for an intent. Anything unusable becomes a harmless look.

    stats, if given, counts {"errors"} and keeps "last_error", so failures are not silent.
    """
    try:
        reply = client.chat(
            build_messages(world, npc_id, memories, feedback), intent_schema(world, npc_id)
        )
        # The actor is filled in by code. The model never chooses who it is.
        return Intent(actor=npc_id, **reply)
    except (LLMError, ValidationError, TypeError) as e:
        if stats is not None:
            stats["errors"] = stats.get("errors", 0) + 1
            stats["last_error"] = str(e)
        return Intent(actor=npc_id, action="look")


def act(
    world: World,
    npc_id: str,
    client,
    memories: Sequence[str] = (),
    stats: dict | None = None,
) -> ActionResult:
    """Decide and act. One retry with the engine's reason, then fall back to look.

    stats, if given, counts {"calls", "rejected", "errors"} so a run can report its rejection rate.
    """
    stats = stats if stats is not None else {}
    feedback = None
    for _ in range(2):
        result = world.act(decide(world, npc_id, client, memories, feedback, stats))
        stats["calls"] = stats.get("calls", 0) + 1
        if result.ok:
            return result
        stats["rejected"] = stats.get("rejected", 0) + 1
        feedback = result.reason
    return world.act(Intent(actor=npc_id, action="look"))
