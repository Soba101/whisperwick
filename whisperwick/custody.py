"""Custody: arrest and release.

Registered in actions.HANDLERS (imported from the bottom of actions.py, so import
actions first, never this file on its own).

The world is physics only. These rules say who CAN hold whom, never who SHOULD be held.
No rule ever arrests anyone because villagers agree: an arrest is only ever the
authority's own chosen action. Every check happens before any change, so a rejected
intent changes nothing.
"""

from whisperwick.actions import MAX_MESSAGE_CHARS, ActionResult, Intent, reject
from whisperwick.events import Event

# Actions a held person cannot do. Talk, look and show stay open: custody stops
# your body and your hands, not your voice.
HELD_BLOCKED = ("move", "take", "drop", "give")


def held_problem(world, intent: Intent) -> str | None:
    """Why this actor is stopped by custody, or None. World.act calls this once for all."""
    holder = world.npcs[intent.actor].held_by
    if holder is not None and intent.action in HELD_BLOCKED:
        return f"you are being held by {holder}"
    return None


def _reason(intent: Intent) -> str:
    """The reason in the actor's own words (the message), trimmed. '' means none given."""
    return (intent.message or "").strip()


def _reason_problem(intent: Intent) -> str | None:
    """Too long is the only way a reason can be wrong. Its content is never judged (#50)."""
    if len(_reason(intent)) > MAX_MESSAGE_CHARS:
        return f"message is longer than {MAX_MESSAGE_CHARS} characters"
    return None


def _log(world, intent: Intent, target) -> ActionResult:
    """Log an arrest or release. Everyone else present, the target included, sees it."""
    here = world.npcs[intent.actor].location
    data = {"target": target.id}
    # Only added when given, so a bare arrest logs exactly as before. Never checked for truth.
    if _reason(intent):
        data["reason"] = _reason(intent)
    event = world.log.append(
        Event(
            tick=world.clock.tick,
            type=intent.action,
            actor=intent.actor,
            location=here,
            data=data,
            witnesses=[n for n in world.npcs_at(here) if n != intent.actor],
        )
    )
    return ActionResult(True, event=event)


def _authority_problem(world, intent: Intent) -> str | None:
    """Only people the scenario names as authority may hold or free anyone."""
    if intent.actor not in world.authority:
        return "you have no authority to do that"
    return None


def do_arrest(world, intent: Intent) -> ActionResult:
    """Hold someone who is here, alive and free. Only an authority who is free may."""
    problem = _authority_problem(world, intent)
    problem = problem or _reason_problem(intent)
    if problem:
        return reject(problem)
    me = world.npcs[intent.actor]
    if me.held_by is not None:
        return reject(f"you are being held by {me.held_by}")
    target = world.npcs.get(intent.target or "")
    if target is None:
        return reject(f"unknown npc {intent.target}")
    if target.id == me.id:
        return reject("you cannot arrest yourself")
    if not target.alive:
        return reject(f"{target.id} is dead")
    if target.location != me.location:
        return reject(f"{target.id} is not here")
    if target.held_by is not None:
        return reject(f"{target.id} is already held by {target.held_by}")
    target.held_by = me.id
    return _log(world, intent, target)


def do_release(world, intent: Intent) -> ActionResult:
    """Let a held person here go. Only an authority may."""
    problem = _authority_problem(world, intent)
    problem = problem or _reason_problem(intent)
    if problem:
        return reject(problem)
    target = world.npcs.get(intent.target or "")
    if target is None:
        return reject(f"unknown npc {intent.target}")
    if target.held_by is None:
        return reject(f"{target.id} is not held")
    if target.location != world.npcs[intent.actor].location:
        return reject(f"{target.id} is not here")
    target.held_by = None
    return _log(world, intent, target)
