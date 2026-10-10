"""Thinking: a villager works out, in its own words, who it suspects and who it trusts.

This replaces the old nightly reflection. The model decides everything. The code only
checks that every memory the villager cites is one it really has, and keeps a record.
A suspect with no valid citation is kept, but marked as a "hunch" (the #11 measure).
Agent side only: never part of World state or state_hash.
"""

from typing import NamedTuple

from whisperwick import aims, belief_text
from whisperwick.belief_log import BeliefLog
from whisperwick.llm_client import LLMError
from whisperwick.memory import Memory, MemoryStream
from whisperwick.thought_people import people_ids, shown_memories
from whisperwick.thought_schema import (  # noqa: F401  (limits are re-exported for callers)
    LEVELS,
    MAX_BECAUSE,
    MAX_TRUST,
    OF_WHAT_MAX_CHARS,
    SURENESS,
    THOUGHTS_MAX_CHARS,
    WHY_MAX_CHARS,
    schema,
)

REFLECTION_IMPORTANCE = 8

def messages(world, npc_id, personality, shown: dict[str, Memory], previous) -> list[dict]:
    """In character, first person. Without this the model answers as an assistant."""
    me = world.npcs[npc_id]
    # No line saying "the mayor was killed": a real villager only knows that if it saw
    # the body or was told. What it knows is in its memories, nowhere else.
    _, trusted = people_ids(world, npc_id)
    lines = [
        f"You are {me.name} ({me.id}), the village {me.occupation}. Stay in character.",
        *belief_text.character_lines(personality),
        "People you may have met: " + ", ".join(belief_text.who(world, n) for n in trusted),
        "Your memories, each with its id:",
        *(f"[{mid}] {m.text}" for mid, m in shown.items()),
    ]
    # #43: plain custody facts only (Sarah was held all day, yet her thoughts said "released").
    lines += belief_text.custody_facts(world, npc_id)
    if previous:
        lines += ["Your last thoughts (you may change your mind):"]
        lines += belief_text.belief_lines(world, previous, npc_id, with_aim=False)
        # Here the aim is offered back to be continued, changed or dropped.
        if aims.active(previous):
            lines.append(f"Your aim: {aims.active(previous)}")
    lines += [
        "Reply only with JSON. Use exact ids, never names.",
        "Only rely on the memories listed. Never invent objects, records or events.",
    ]
    # An open question: what is going on, as far as I know? Nothing here hints at the plot.
    ask = (
        "Think to yourself, in first person. What do you make of what has been happening? "
        "Who, if anyone, do you truly believe has done something bad, of what, and how sure "
        "are you? Which of your memories make you think so (give their ids)? "
        "Do you mean to accuse anyone out loud? If so, who? "
        + aims.ASK + " "
        "And how do you feel about the people you have met, and why?"
    )
    return [
        {"role": "system", "content": "\n".join(lines)},
        {"role": "user", "content": ask},
    ]


def checked(reply: dict, shown: dict[str, Memory], world, npc_id: str, stats: dict) -> dict:
    """Keep only what is real. Raises on a reply that is not usable at all."""
    suspects, trusted = people_ids(world, npc_id)
    suspect, sureness = reply["suspect"], reply["sureness"]
    # .get(): older fake clients in tests send no of_what. Only kept with a suspect.
    of_what = " ".join(str(reply.get("of_what") or "").split())[:OF_WHAT_MAX_CHARS] or None
    of_what = of_what if suspect is not None else None
    if suspect is not None and suspect not in suspects:
        raise ValueError(f"unknown suspect {suspect}")
    # .get(): older fake clients send no will_accuse. It is only an intention, so it may be
    # anyone alive but me, whatever the suspect is.
    will_accuse = reply.get("will_accuse")
    if will_accuse is not None and will_accuse not in trusted:
        raise ValueError(f"unknown will_accuse {will_accuse}")
    aim, aim_status = aims.checked(reply)  # raises on a bad status
    if sureness not in SURENESS:
        raise ValueError(f"unknown sureness {sureness}")
    if not isinstance(reply["because"], list):
        raise TypeError("because must be a list")
    # A cited id must be one of the memories shown. Fakes are dropped and counted.
    because: list[dict] = []
    for mid in reply["because"]:
        if mid not in shown:
            stats["bad_citations"] = stats.get("bad_citations", 0) + 1
        elif mid not in [b["memory_id"] for b in because]:
            m = shown[mid]
            because.append({"memory_id": mid, "event_id": m.event_id, "text": m.text})
    # People the villager rates: only real, living, other people. One entry each.
    trust: list[dict] = []
    for t in reply["trust"]:
        if t["person"] in trusted and t["level"] in LEVELS:
            if t["person"] not in [x["person"] for x in trust]:
                why = " ".join(str(t["why"]).split())[:WHY_MAX_CHARS]
                trust.append({"person": t["person"], "level": t["level"], "why": why})
    # The server does not always enforce maxLength, so trim here and flatten newlines.
    thoughts = " ".join(str(reply["thoughts"]).split())[:THOUGHTS_MAX_CHARS]
    return {"suspect": suspect, "of_what": of_what, "sureness": sureness, "thoughts": thoughts,
            "will_accuse": will_accuse, "aim": aim, "aim_status": aim_status,
            "because": because[:MAX_BECAUSE], "trust": trust[:MAX_TRUST]}  # fmt: skip


class Prepared(NamedTuple):
    """Everything one thinking call needs. Built in the main thread; the call may run anywhere."""

    shown: dict[str, Memory]
    messages: list[dict]
    schema: dict


def prepare(stream, npc_id, world, personality, belief_log) -> Prepared | None:
    """Read this villager's own memories and the world; build the call. None = nothing to think."""
    shown = shown_memories(stream)
    if not shown:
        return None  # nothing to think about yet, and an empty enum is not a valid schema
    prompt = messages(world, npc_id, personality, shown, belief_log.latest(npc_id))
    return Prepared(shown, prompt, schema(world, npc_id, list(shown)))


def finish(
    stream: MemoryStream,
    npc_id: str,
    world,
    tick: int,
    belief_log: BeliefLog,
    prepared: Prepared,
    outcome,
    stats: dict,
) -> dict | None:
    """Turn the call's reply (or the exception it raised) into a record. None if it failed."""
    shown = prepared.shown
    try:
        if isinstance(outcome, BaseException):
            raise outcome
        record = checked(outcome, shown, world, npc_id, stats)
    except (LLMError, KeyError, TypeError, ValueError) as e:
        # A missed thought is fine: the next one will catch up. Count it, never crash.
        stats["thought_errors"] = stats.get("thought_errors", 0) + 1
        stats["last_thought_error"] = str(e)
        return None
    # No valid citation for a suspect means the belief rests on nothing it remembers.
    hunch = record["suspect"] is not None and not record["because"]
    if hunch:
        stats["hunches"] = stats.get("hunches", 0) + 1
    events = world.log.all()
    record.update(
        tick=tick, npc=npc_id, hunch=hunch,
        # Everything up to this event id was already said when the villager thought.
        after_event=events[-1].id if events else 0,
    )  # fmt: skip
    stream.add(tick, record["thoughts"], REFLECTION_IMPORTANCE, "reflection")
    belief_log.add(record)
    return record


def think(
    stream: MemoryStream,
    npc_id: str,
    world,
    client,
    tick: int,
    personality: str | None,
    belief_log: BeliefLog,
    stats: dict | None = None,
) -> dict | None:
    """One thought. Returns the new belief record, or None if the model failed.

    Stores a reflection memory (what the villager remembers thinking) and a belief record.
    stats, if given, counts bad_citations, hunches and thought_errors.
    The parallel run loop calls prepare and finish itself, with the model calls in between.
    """
    stats = stats if stats is not None else {}
    prepared = prepare(stream, npc_id, world, personality, belief_log)
    if prepared is None:
        return None
    try:
        outcome = client.chat(prepared.messages, prepared.schema)
    except (LLMError, KeyError, TypeError, ValueError) as e:
        outcome = e
    return finish(stream, npc_id, world, tick, belief_log, prepared, outcome, stats)
