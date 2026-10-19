"""Who told whom, using only logged claims and belief citations. No model calls."""

from whisperwick.belief_log import BeliefLog
from whisperwick.claims import claim_words
from whisperwick.clock import Clock
from whisperwick.events import Event


def compact(text: str, limit: int = 200) -> str:
    """Keep each receipt on one line so long diaries do not bury the chain."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 3] + "..."


def render(events: list[Event], log: BeliefLog | None, subject: str) -> str:
    """Print tagged talks in event order, their cited sources, then custody outcomes.

    A shared subject does not prove that two claims are the same story. Only a
    citation is drawn as an edge. Belief numbers are positions in the saved log.
    """
    events = sorted(events, key=lambda e: e.id)
    by_id = {e.id: e for e in events}
    talks = [e for e in events if e.type == "talk"
             and (e.data.get("claim") or {}).get("subject") == subject]
    custody = [e for e in events if e.type in ("arrest", "release")
               and e.data.get("target") == subject]
    records = log.records if log else []
    # Keep the actual record, even if its suspect differs from the spoken claim.
    preceding = {e.id: log.before(e.actor, e.id) if log else None for e in talks + custody}
    numbers = {id(r): i for i, r in enumerate(records, 1)}
    talk_ids = {e.id for e in talks}
    used = {id(r) for r in preceding.values() if r is not None}
    relevant = [r for r in records if id(r) in used or r.get("suspect") == subject
                or any(c.get("event_id") in talk_ids for c in r.get("because", []))]

    def before(e: Event) -> str:
        record = preceding[e.id]
        return f"b{numbers[id(record)]}" if record is not None else "no logged belief"

    out = [f"Spread of {subject} (logged claims; citations are not proof of causation):",
           "Claims in event order:"]
    for e in talks:
        claim = e.data["claim"]
        tag = " [unverified tag]" if claim.get("unverified") else ""
        heard = ", ".join(e.witnesses) or "nobody"
        out += [f"  e{e.id} {Clock(e.tick).label()} {e.actor} -> {e.data.get('to')}: "
                f"{claim_words(claim, subject)}{tag}",
                f'    said: "{compact(e.data["message"], 500)}"',
                f"    witnesses: {heard}; preceding belief: {before(e)}"]
    if not talks:
        out.append("  No tagged claims about this subject.")
    out.append("Beliefs and cited memories (bN = saved belief record N):")
    for r in relevant:
        out += [f"  b{numbers[id(r)]} {r['npc']} after e{r['after_event']}: "
                f"suspect={r.get('suspect')}; {r.get('sureness')}",
                f'    thought: "{compact(r.get("thoughts", ""))}"']
        if not r.get("because"):
            out.append("    no cited memories")
        for c in r.get("because", []):
            eid = c.get("event_id")
            event = by_id.get(eid)
            source = f"e{eid} (event unavailable)" if eid is not None else "no event"
            if event:
                if event.type == "talk":
                    # Own words are not an independent witness. Do not imply otherwise.
                    how = "own words" if event.actor == r["npc"] else (
                        "heard" if r["npc"] in event.witnesses else "not a recorded witness")
                    source = f"e{eid} {how}: {event.actor} -> {event.data.get('to')}"
                else:
                    source = f"e{eid} {event.type} by {event.actor}"
            out.append(f'    {c["memory_id"]} -> {source}: "{compact(c.get("text", ""))}"')
    if log is None:
        # Old runs still have useful talk and custody receipts.
        out.append("  No belief log; citation links unavailable.")
    elif not relevant:
        out.append("  No relevant beliefs logged.")
    out.append("Custody outcomes:")
    for e in custody:
        out += [f"  e{e.id} {Clock(e.tick).label()} {e.actor} {e.type} {subject}; "
                f"preceding belief: {before(e)}",
                f'    reason: "{compact(e.data.get("reason", ""))}"']
    if not custody:
        out.append("  No arrest/release of this subject.")
    return "\n".join(out)
