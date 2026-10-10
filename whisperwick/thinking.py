"""Thinking: a villager works out, in its own words, who it suspects and who it trusts.

This replaces the old nightly reflection. The model decides everything. The code only
checks that every memory the villager cites is one it really has, and keeps a record.
A suspect with no valid citation is kept, but marked as a "hunch" (the #11 measure).
Agent side only: never part of World state or state_hash.
"""

from whisperwick import aims, belief_text
from whisperwick.belief_log import BeliefLog
from whisperwick.llm_client import LLMError
from whisperwick.memory import Memory, MemoryStream
from whisperwick.thought_people import people_ids, shown_memories

REFLECTION_IMPORTANCE = 8
THOUGHTS_MAX_CHARS = 400  # a thought is a few sentences, never an essay
WHY_MAX_CHARS = 150
OF_WHAT_MAX_CHARS = 100  # e.g. "killing the mayor", in the villager's own words
MAX_BECAUSE = 5
MAX_TRUST = 6
SURENESS = ["unsure", "fairly sure", "certain"]
LEVELS = ["low", "medium", "high"]


def schema(world, npc_id: str, memory_ids: list[str]) -> dict:
    """Enums everywhere, so the model can only name real people and memories it was shown."""
    suspects, trusted = people_ids(world, npc_id)
    return {
        "type": "object",
        "properties": {
            "thoughts": {"type": "string", "maxLength": THOUGHTS_MAX_CHARS},
            # Who they truly believe did it (their private belief).
            "suspect": {"enum": [*suspects, None]},
            # What they suspect that person of, in their own words. The code never names a crime:
            # a villager only knows about the murder if it saw the body or was told.
            "of_what": {"type": ["string", "null"], "maxLength": OF_WHAT_MAX_CHARS},
            "sureness": {"enum": SURENESS},
            # Who they mean to accuse out loud, if anyone. May differ from suspect: that is
            # how belief and intention are recorded apart. Only living others can be named.
            "will_accuse": {"enum": [*trusted, None]},
            # What they want to do next, in their own words (see aims.py). May be null.
            **aims.schema_properties(),
            "because": {"type": "array", "maxItems": MAX_BECAUSE, "items": {"enum": memory_ids}},
            "trust": {
                "type": "array",
                "maxItems": MAX_TRUST,
                "items": {
                    "type": "object",
                    "properties": {
                        "person": {"enum": trusted},
                        "level": {"enum": LEVELS},
                        "why": {"type": "string", "maxLength": WHY_MAX_CHARS},
                    },
                    "required": ["person", "level", "why"],
                },
            },
        },
        "required": [
            "thoughts", "suspect", "of_what", "sureness", "will_accuse", "aim", "aim_status",
            "because", "trust",
        ],  # fmt: skip
    }


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
    """
    stats = stats if stats is not None else {}
    shown = shown_memories(stream)
    if not shown:
        return None  # nothing to think about yet, and an empty enum is not a valid schema
    prompt = messages(world, npc_id, personality, shown, belief_log.latest(npc_id))
    try:
        reply = client.chat(prompt, schema(world, npc_id, list(shown)))
        record = checked(reply, shown, world, npc_id, stats)
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
