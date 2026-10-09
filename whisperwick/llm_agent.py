"""An NPC that is driven by a language model.

The model only proposes an Intent. The engine (World.act) still decides
what really happens. We never trust the model's output without that check.
"""

from collections.abc import Sequence

from pydantic import ValidationError

from whisperwick import belief_text
from whisperwick.actions import ActionResult, Intent
from whisperwick.llm_client import LLMError
from whisperwick.llm_intent import exits_and_people, intent_schema, item_lines
from whisperwick.memory import MemoryStream
from whisperwick.repeat_guard import ActionHistory, repeat_reason
from whisperwick.world import World


def build_messages(
    world: World,
    npc_id: str,
    memories: Sequence[str] = (),
    feedback: str | None = None,
    # Week 4, all optional: with none of them the prompt has no character or belief.
    personality: str | None = None,
    belief: dict | None = None,  # this villager's latest record in the belief log
    history: ActionHistory | None = None,
) -> list[dict]:
    """One compact system message: who I am, where I am, who and what is around."""
    me = world.npcs[npc_id]
    exits, people = exits_and_people(world, npc_id)
    here = world.locations[me.location]
    lines = [
        f"You are {me.name} ({me.id}), the village {me.occupation}.",
        # Who I am as a person, then what I last worked out, in my own words.
        *belief_text.character_lines(personality),
        *belief_text.belief_lines(world, belief, npc_id),
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
    # What I already said to the people in front of me, so I can see when I repeat myself.
    lines += belief_text.last_words(world, history, npc_id, people)
    lines.append(belief_text.CLAIM_RULE)
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


def decide(
    world: World,
    npc_id: str,
    client,
    memories: Sequence[str] = (),
    feedback: str | None = None,
    stats: dict | None = None,
    personality: str | None = None,
    belief: dict | None = None,
    history: ActionHistory | None = None,
) -> Intent:
    """Ask the model for an intent. Anything unusable becomes a harmless look.

    stats, if given, counts {"errors"} and keeps "last_error", so failures are not silent.
    """
    try:
        reply = dict(
            client.chat(
                build_messages(world, npc_id, memories, feedback, personality, belief, history),
                intent_schema(world, npc_id),
            )
        )
        # The two flat claim fields become one Claim, but only on a talk with both set.
        # Anything else is model noise and is dropped quietly, not counted as an error.
        # pop(key, None) keeps old clients that never send the fields working.
        kind, subject = reply.pop("claim_kind", None), reply.pop("claim_subject", None)
        if reply.get("action") == "talk" and kind and subject:
            reply["claim"] = {"kind": kind, "subject": subject}
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
    personality: str | None = None,
    belief: dict | None = None,
    history: ActionHistory | None = None,
) -> ActionResult:
    """Decide and act. One retry with the engine's reason, then fall back to look.

    stats, if given, counts {"calls", "rejected", "errors", "repeats"}
    so a run can report its rejection rate.
    """
    stats = stats if stats is not None else {}
    feedback = None
    for _ in range(2):
        intent = decide(
            world, npc_id, client, memories, feedback, stats, personality, belief, history
        )
        # Repeat guard (#12): refuse a pointless repeat before the engine sees it.
        # It counts as a rejection, so the one-retry flow below stays the same.
        reason = repeat_reason(world, history, intent) if history is not None else None
        if reason:
            stats["repeats"] = stats.get("repeats", 0) + 1
            result = ActionResult(False, reason)
        else:
            result = world.act(intent)
            if result.ok and history is not None:
                history.record(world.clock.tick, intent)
        stats["calls"] = stats.get("calls", 0) + 1
        if result.ok:
            return result
        stats["rejected"] = stats.get("rejected", 0) + 1
        feedback = result.reason
    return world.act(Intent(actor=npc_id, action="look"))
