"""Small gestures are witnessed words, never a way to bypass the physics."""

import re

from whisperwick.action_types import ActionResult, reject
from whisperwick.events import Event

MAX_GESTURE_CHARS = 80
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
    r"hand(?:s|ed|ing)\s+\w+|"
    r"(?:walk(?:s|ed|ing)?|run(?:s|ning)?|go(?:es|ing)?|went|head(?:s|ed|ing)?)"
    r"\s+(?:to|into|out|through|towards?)\b|"
    r"lock(?:s|ed|ing)?|unlock(?:s|ed|ing)?|reveal(?:s|ed|ing)?)\b", re.I,
)


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
    text = (intent.text or "").strip()
    if not text:
        return reject("gesture text is empty")
    if len(text) > MAX_GESTURE_CHARS or any(c in text for c in "\n\r\t"):
        return reject(f"gesture must be one line of at most {MAX_GESTURE_CHARS} characters")
    if PHYSICAL.search(text):
        return reject("gesture claims a physical result; use a physical action")
    for item in world.items.values():
        words = [item.id, item.name, *(w for w in item.name.split() if len(w) >= 3)]
        if any(has_word(text, w) for w in words):
            return reject("gesture names an item; use an item action")
    here = world.npcs[intent.actor].location
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
