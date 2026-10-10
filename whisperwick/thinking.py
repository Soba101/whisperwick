"""Thinking: a villager works out, in its own words, who it suspects and who it trusts.

This replaces the old nightly reflection. The model decides everything. The code only
checks that every memory the villager cites is one it really has, and keeps a record.
A suspect with no valid citation is kept, but marked as a "hunch" (the #11 measure).
Agent side only: never part of World state or state_hash.
"""

from typing import NamedTuple

from whisperwick import aims
from whisperwick.belief_log import BeliefLog
from whisperwick.llm_client import LLMError
from whisperwick.memory import Memory, MemoryStream
from whisperwick.recall import Private
from whisperwick.thought_people import people_ids, shown_memories
from whisperwick.thought_prompt import messages  # noqa: F401  (re-exported)
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
    # Week 6: is villager memory on, and what did a recall (round 1) search for and find?
    memory: bool = False
    recall: str | None = None
    recalled: tuple[str, ...] = ()


def prepare(
    stream, npc_id, world, personality, belief_log, private: Private | None = None
) -> Prepared | None:
    """Read this villager's own memories and the world; build the call. None = nothing to think.

    With private (villager memory on) the prompt shows the notebook and the schema offers
    recall and notebook fields. Without it everything is as before week 6.
    """
    shown = shown_memories(stream)
    if not shown:
        return None  # nothing to think about yet, and an empty enum is not a valid schema
    notebook = private.notebooks.lines(npc_id, world) if private else None
    prompt = messages(world, npc_id, personality, shown, belief_log.latest(npc_id), notebook)
    sch = schema(world, npc_id, list(shown), memory=bool(private), recall=bool(private))
    return Prepared(shown, prompt, sch, memory=bool(private))


def finish(
    stream: MemoryStream,
    npc_id: str,
    world,
    tick: int,
    belief_log: BeliefLog,
    prepared: Prepared,
    outcome,
    stats: dict,
    private: Private | None = None,
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
    if private:
        # Only now, once the thought is known to be usable, does the notebook change.
        private.notebooks.apply(npc_id, outcome, people_ids(world, npc_id)[1])
        record.update(
            recall=prepared.recall, recalled=list(prepared.recalled),
            notebook=private.notebooks.to_dict().get(npc_id, {"me": None, "people": {}}),
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
