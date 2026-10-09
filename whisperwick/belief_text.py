"""Words for the prompt: goal, beliefs, trust and last words. Pure text, no state changes.

Everything here is read from BeliefState / ActionHistory, so the model sees what the
code knows. The model is told what it believes and why; it never decides that.
"""

from whisperwick.beliefs import BeliefState
from whisperwick.clock import Clock
from whisperwick.repeat_guard import ActionHistory, Record

MAX_BELIEFS = 3  # keep the prompt short for a small model
MAX_QUOTE = 80  # longest quoted message in "last words"

# Said once, after the lists, because the schema alone cannot explain it.
CLAIM_RULE = (
    "To spread what you believe, or a lie, add claim_kind (killer or innocent) and "
    "claim_subject (a person id) to a talk. Only claims change what others believe."
)


def who(world, person_id: str) -> str:
    return f"{world.npcs[person_id].name} ({person_id})"


def why(world, sources) -> str:
    """First-hand notes (no repeats), then 'told by X (id) xN', grouped by teller."""
    seen: list[str] = []
    told: dict[str, int] = {}
    for s in sources:
        if s.type == "saw":
            if s.note not in seen:
                seen.append(s.note)
        else:
            told[s.by] = told.get(s.by, 0) + 1
    # Notes are already worded as facts ("saw Victor hurrying ..."), so show them as they are.
    parts = list(seen)
    for teller, count in told.items():
        parts.append(f"told by {who(world, teller)}" + (f" x{count}" if count > 1 else ""))
    return "; ".join(parts)


def belief_lines(world, beliefs: BeliefState, npc_id: str) -> list[str]:
    """Top suspects first (highest confidence, ties by id), each with its reasons."""
    conf = beliefs.conf.get(npc_id, {})
    ranked = sorted((s for s in conf if conf[s] > 0), key=lambda s: (-conf[s], s))
    if not ranked:
        return []
    lines = ["What you believe about the murder:"]
    for subject in ranked[:MAX_BELIEFS]:
        percent = round(conf[subject] * 100)
        # You know whether you did it yourself, so say so plainly.
        name = "You" if subject == npc_id else who(world, subject)
        reasons = why(world, beliefs.sources.get(npc_id, {}).get(subject, []))
        lines.append(f"- {name} did it: {percent}%." + (f" Why: {reasons}" if reasons else ""))
    return lines


def trust_line(world, beliefs: BeliefState, npc_id: str, people: list[str]) -> list[str]:
    """How much I trust each person here, sorted by id."""
    if not people:
        return []
    bits = [
        f"{world.npcs[p].name} {round(beliefs.trust.get(npc_id, p) * 100)}%" for p in sorted(people)
    ]
    return ["Trust in people here: " + ", ".join(bits)]


def points_to_marks(beliefs: BeliefState | None, npc_id: str) -> dict[str, str]:
    """Items whose clue is this NPC get a warning. Empty when there are no beliefs."""
    if beliefs is None:
        return {}
    return {i: " - this points to you!" for i, p in sorted(beliefs.clues.items()) if p == npc_id}


def say_of(world, r: Record) -> str:
    """One past act in words: 'told Bob (npc_bob) "hi" ...'."""
    when = Clock(r.tick).label()
    to = "everyone here" if r.target is None else who(world, r.target)
    if r.action == "talk":
        text = (r.message or "")[:MAX_QUOTE]
        line = f'told {to} "{text}"'
        if r.claim:
            line += f" (claim: {r.claim[0]} {who(world, r.claim[1])})"
        return f"{line} at {when}"
    item = world.items[r.item].name if r.item in world.items else r.item
    verb = "showed" if r.action == "show" else "gave"
    return f"{verb} {item} to {to} at {when}"


def last_words(world, history: ActionHistory | None, npc_id: str, people: list[str]) -> list[str]:
    """My last 3 words or items for the people in front of me, so I see if I repeat myself."""
    if history is None:
        return []
    records = history.recent_to(npc_id, people)
    if not records:
        return []
    return ["Your last words here:", *[f"- {say_of(world, r)}" for r in records]]
