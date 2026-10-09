"""Item actions: take, drop, give, show.

Registered in actions.HANDLERS (this module is imported from the bottom of
actions.py, so import actions first, never this file on its own).
Every check happens before any change, so a rejected intent changes nothing.
"""

from whisperwick.actions import ActionResult, Intent, reject
from whisperwick.events import Event


def _log(world, intent: Intent, item, to: str | None = None) -> ActionResult:
    """Log one item event. Everyone alive in the room, except the actor, sees it."""
    here = world.npcs[intent.actor].location
    # The item's name and description are copied in, so memories and stories
    # can describe it later without looking at the world again.
    data = {"item": item.id, "item_name": item.name, "item_description": item.description}
    if to:
        data["to"] = to
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


def _held_item(world, intent: Intent):
    """The item the actor holds, or a rejection reason (as a string)."""
    item = world.items.get(intent.item or "")
    if item is None:
        return f"unknown item {intent.item}"
    if item.holder != intent.actor:
        return f"you are not holding {item.id}"
    return item


def _person_here(world, intent: Intent) -> str | None:
    """Why the target cannot receive/see an item, or None if they can."""
    other = world.npcs.get(intent.target or "")
    if other is None:
        return f"unknown npc {intent.target}"
    if other.id == intent.actor:
        return "cannot do that with yourself"
    if not other.alive:
        return f"{other.id} is dead"
    if other.location != world.npcs[intent.actor].location:
        return f"{other.id} is not here"
    return None


def do_take(world, intent: Intent) -> ActionResult:
    """Pick up an item lying on the ground here."""
    item = world.items.get(intent.item or "")
    if item is None:
        return reject(f"unknown item {intent.item}")
    if item.location != world.npcs[intent.actor].location:
        return reject(f"{item.id} is not here")
    item.holder, item.location = intent.actor, None
    return _log(world, intent, item)


def do_drop(world, intent: Intent) -> ActionResult:
    """Put a held item on the ground where you stand."""
    item = _held_item(world, intent)
    if isinstance(item, str):
        return reject(item)
    item.location, item.holder = world.npcs[intent.actor].location, None
    return _log(world, intent, item)


def do_give(world, intent: Intent) -> ActionResult:
    """Hand a held item to a living person in the same place."""
    item = _held_item(world, intent)
    if isinstance(item, str):
        return reject(item)
    problem = _person_here(world, intent)
    if problem:
        return reject(problem)
    item.holder = intent.target
    return _log(world, intent, item, to=intent.target)


def do_show(world, intent: Intent) -> ActionResult:
    """Show a held item to the room, or to one person. Nothing moves."""
    item = _held_item(world, intent)
    if isinstance(item, str):
        return reject(item)
    if intent.target is not None:
        problem = _person_here(world, intent)
        if problem:
            return reject(problem)
    return _log(world, intent, item, to=intent.target)
