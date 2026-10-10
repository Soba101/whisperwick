"""Explain one event: what happened, who saw it, and what the actor thought just before.

An event in the log was ACCEPTED by the world. Rejected intents are never logged, so
this cannot explain them (the run's stats count rejections, nothing more).
The thinking shown is the actor's newest belief record made before the event
(npc == actor and after_event < N). Belief records are model output, so they are
shown as "what they said they thought", never as fact. No model is called.
"""

from whisperwick import story
from whisperwick.belief_log import BeliefLog
from whisperwick.claims import claim_words
from whisperwick.clock import Clock
from whisperwick.events import Event


def what_happened(e: Event, names: dict[str, str]) -> str:
    """Story's wording when it has one (talk, move, items, custody), else a plain fallback."""
    line = story.format_event(e, names)
    if line:
        # Kept whole (time and place included), so it reads the same as the story file.
        return line
    return f"{story.show(names, e.actor)} {e.type} {e.data}"


def claim_lines(e: Event, names: dict[str, str]) -> list[str]:
    """For a talk with a claim: the claim and whether the engine tagged it unverified."""
    claim = e.data.get("claim") if e.type == "talk" else None
    if not claim:
        return []
    words = claim_words(claim, story.show(names, claim["subject"]))
    return [f"Claim: {words} (unverified: {'yes' if claim.get('unverified') else 'no'})"]


def thinking_lines(record: dict | None, names: dict[str, str]) -> list[str]:
    """The actor's last thinking before the event. Old records lack some keys: use .get()."""
    if record is None:
        return ["Thinking before this event: no thinking before this event"]
    suspect = record.get("suspect")
    who = story.show(names, suspect) if suspect else "nobody"
    of_what = f" of {record['of_what']}" if record.get("of_what") else ""
    out = [
        f"Thinking before this event (after event {record['after_event']}):",
        f"  suspect: {who}{of_what}, sureness: {record.get('sureness')}",
        f"  will accuse: {record.get('will_accuse')}",
        f"  aim: {record.get('aim')} (status: {record.get('aim_status')})",
        f'  thoughts: "{record.get("thoughts", "")}"',
    ]
    because = record.get("because") or []
    if because:
        out.append("  cited memories:")
        out += [f'    {c["memory_id"]}: "{c["text"]}"' for c in because]
    elif suspect:
        # A suspect with nothing cited is a guess, and we say so.
        out.append("  acted on a hunch (no cited memory)")
    return out


def explain(
    events: list[Event], log: BeliefLog | None, event_id: int, names: dict[str, str]
) -> str:
    """The whole explanation. Raises ValueError if no event has this id."""
    e = next((x for x in events if x.id == event_id), None)
    if e is None:
        raise ValueError(f"No event {event_id} in this run.")
    seen = ", ".join(story.show(names, w) for w in e.witnesses) or "nobody"
    out = [
        f"Event {e.id}: {what_happened(e, names)}",
        f"  who: {story.show(names, e.actor)}  where: {story.show(names, e.location)}"
        f"  when: {Clock(e.tick).label()}  seen by: {seen}",
        "  The world accepted this (rejected intents are not logged).",
        *claim_lines(e, names),
        "",
    ]
    if log is None:
        return "\n".join([*out, "No belief log for this run (an older run?)."])
    return "\n".join([*out, *thinking_lines(log.before(e.actor, e.id), names)])
