"""Words for the prompt: character, what I think, who I trust, and my last words.

Pure text, no state changes. A villager's belief is shown in the villager's own words,
as it said them when it last thought. No numbers from code, no verdicts from code.
"""

from whisperwick.claims import claim_words
from whisperwick.clock import Clock
from whisperwick.repeat_guard import ActionHistory, Record

MAX_QUOTE = 80  # longest quoted message in "last words"

# Said once, after the lists, because the schema alone cannot explain it.
# A claim is the villager choosing to speak out. It is not a belief change.
CLAIM_RULE = (
    "If your words openly accuse someone, set accuses to their id. "
    "If your words openly defend someone, set defends to their id. "
    "Otherwise leave both null."
)


def who(world, person_id: str) -> str:
    return f"{world.npcs[person_id].name} ({person_id})"


def character_lines(personality: str | None) -> list[str]:
    """The villager's temperament, from the scenario. Character, not plot."""
    return [f"Your character: {personality}"] if personality else []


def suspect_phrase(world, record: dict, npc_id: str) -> str:
    """e.g. 'you suspect Victor (npc_victor) of killing the mayor, fairly sure'.

    Uses the villager's own words (of_what). Nothing here assumes there was a murder.
    """
    suspect = record["suspect"]
    if suspect is None:
        return "you don't suspect anyone of anything yet"
    # .get(): records written before of_what existed have no such key.
    of_what = f" of {record['of_what']}" if record.get("of_what") else ""
    if suspect == npc_id:
        # The villager suspects itself: it knows what it did.
        return f"you know you are guilty{of_what}"
    return f"you suspect {who(world, suspect)}{of_what}, {record['sureness']}"


def belief_lines(world, record: dict | None, npc_id: str) -> list[str]:
    """My latest thoughts and trust, from my newest belief record. Empty if I never thought."""
    if record is None:
        return []
    phrase = suspect_phrase(world, record, npc_id)
    # .get(): records written before will_accuse existed have no such key.
    meant = record.get("will_accuse")
    out_loud = f" You mean to accuse {who(world, meant)} out loud." if meant else ""
    lines = [f"What you think right now: {phrase}.{out_loud} {record['thoughts']}"]
    # Only people who still exist in this world; the model's own words about each.
    feel = [
        f"{who(world, t['person'])} {t['level']}: {t['why']}"
        for t in record["trust"]
        if t["person"] in world.npcs
    ]
    if feel:
        lines.append("How you feel about people: " + "; ".join(feel))
    return lines


def say_of(world, r: Record) -> str:
    """One past act in words: 'told Bob (npc_bob) "hi" ...'."""
    when = Clock(r.tick).label()
    to = "everyone here" if r.target is None else who(world, r.target)
    if r.action == "talk":
        text = (r.message or "")[:MAX_QUOTE]
        line = f'told {to} "{text}"'
        if r.claim:
            line += f" (claim: {claim_words({'kind': r.claim[0]}, who(world, r.claim[1]))})"
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
