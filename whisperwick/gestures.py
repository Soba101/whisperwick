"""Small gestures are witnessed words, never a way to bypass the physics."""

import re

from whisperwick.action_types import ActionResult, reject
from whisperwick.events import Event

MAX_GESTURE_CHARS = 120  # 80 refused 1 in 10 live gestures (2026-10-21); still one line
# Inflections are explicit so a result verb such as 'closes' cannot slip through.
PHYSICAL = re.compile(
    r"\b(?:tak(?:e[sn]?|ing)|took|giv(?:e[sn]?|ing)|gave|given|"
    r"open(?:s|ed|ing)?|clos(?:e[sd]?|ing)|shut(?:s|ting)?|"
    r"hit(?:s|ting)?|strik(?:e[sn]?|ing)|struck|punch(?:es|ed|ing)?|"
    r"kick(?:s|ed|ing)?|hid(?:e[sn]?|ing|den)?|"
    r"mov(?:e[sd]?|ing)|push(?:es|ed|ing)?|pull(?:s|ed|ing)?|"
    r"drag(?:s|ged|ging)?|lift(?:s|ed|ing)?|carr(?:y|ies|ied|ying)|"
    r"put(?:s|ting)?|drop(?:s|ped|ping)?|pick(?:s|ed|ing)?|"
    r"throw(?:s|n|ing)?|threw|toss(?:es|ed|ing)?|"
    r"lead(?:s|ing)?|led|bring(?:s|ing)?|brought|"
    r"grab(?:s|bed|bing)?|steal(?:s|ing)?|stole[n]?|"
    r"break(?:s|ing)?|broke[n]?|destroy(?:s|ed|ing)?|"
    r"remov(?:e[sd]?|ing)|snatch(?:es|ed|ing)?|pass(?:es|ed|ing)?|"
    r"kill(?:s|ed|ing)?|stab(?:s|bed|bing)?|smash(?:es|ed|ing)?|"
    # "hands" alone is a body part ("wipes his hands"); only handing something over counts.
    r"hand(?:s|ed|ing)?\s+(?:over\b|(?!(?:with|on|in|to|together|behind|into|against|at|and)\b)"
    r"\w+\s+(?:a|an|the|his|her|their|some|my)\b)|"
    r"(?:walk(?:s|ed|ing)?|run(?:s|ning)?|go(?:es|ing)?|went|head(?:s|ed|ing)?)"
    r"\s+(?:to|into|out|through|towards?)\b|"
    r"lock(?:s|ed|ing)?|unlock(?:s|ed|ing)?|reveal(?:s|ed|ing)?)\b", re.I,
)


# Speech belongs in talk: a gesture with a question, quotes or someone addressed is words.
SPEECH = re.compile(r'[?"\u201c\u201d]|\b(?:[Yy]ou|[Yy]our|I|I\'m|I\'ll)\b')


def has_word(text: str, word: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.I))


def gesture_line(text: str, who: str, actor_id: str | None = None) -> str:
    """Replies may include the actor's name or just the gesture itself."""
    name = who.split(" (")[0]
    for prefix in (name, actor_id):
        if prefix and text.casefold().startswith(prefix.casefold() + " "):
            return who + text[len(prefix):]
    return f"{who} {text}"


def do_gesture(world, intent) -> ActionResult:
    if intent.actor == "player":
        return reject("gestures are villagers only")
    # Models put the gesture in `message`, the field talk uses (2026-10-21 runs: almost
    # every gesture was refused as empty). `text` still works for older replies.
    text = (intent.message or intent.text or "").strip()
    if not text:
        return reject("gesture text is empty")
    if len(text) > MAX_GESTURE_CHARS or any(c in text for c in "\n\r\t"):
        return reject(f"gesture must be one line of at most {MAX_GESTURE_CHARS} characters")
    # Ids are for the engine; a witnessed gesture reads as prose.
    # The actor's own id may lead the line ("npc_bob paces"); gesture_line turns it into a name.
    if any(i != intent.actor for i in re.findall(r"\b(?:item|npc|loc)_\w+", text)):
        return reject("a gesture uses names, not ids")
    if SPEECH.search(text):
        return reject("a gesture has no words; use talk to say something")
    if PHYSICAL.search(text):
        return reject("gesture claims a physical result; use a physical action")
    here = world.npcs[intent.actor].location
    # Pointing at boots someone here wears is fine (2026-10-21 runs). Only an item the
    # actor cannot see here would be news the gesture invents, so only those are refused.
    in_view = set(world.items_at(here, intent.actor))
    in_view |= {i for n in world.npcs_at(here) for i in world.items_held(n)}
    for item in world.items.values():
        if item.id in in_view:
            continue
        words = [item.id, item.name, *(w for w in item.name.split() if len(w) >= 3)]
        if any(has_word(text, w) for w in words):
            return reject("gesture names an item that is not here; use an item action")
    for person in world.npcs.values():
        if person.alive and person.location == here:
            continue
        words = [person.id, *person.name.split()]
        if any(has_word(text, w) for w in words):
            return reject(f"{person.id} is not here")
    event = world.log.append(Event(
        tick=world.clock.tick, type="gesture", actor=intent.actor, location=here,
        data={"text": text}, witnesses=[n for n in world.npcs_at(here) if n != intent.actor],
    ))
    return ActionResult(True, event=event)
