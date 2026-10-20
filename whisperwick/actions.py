"""Actions: what an agent can *ask* the world to do.

An agent (stub now, LLM from week 2) returns an Intent.
The engine checks it and either applies it or rejects it with a reason.
Handlers here are the only code that changes NPC state.
"""

import re

from whisperwick.action_types import (  # noqa: F401 (public action API)
    CLAIM_KINDS,
    MAX_MESSAGE_CHARS,
    ActionResult,
    Claim,
    Intent,
    reject,
)
from whisperwick.events import Event


def do_move(world, intent: Intent) -> ActionResult:
    """Walk to a neighbouring location. No teleporting."""
    npc = world.npcs[intent.actor]
    to = intent.target
    if to not in world.locations:
        return reject(f"unknown location {to}")
    here = npc.location
    if to not in world.locations[here].links:
        return reject(f"{to} is not reachable from {here}")

    # Witnesses = anyone at the start or the end of the walk, except the walker.
    # A simple first rule; perception gets smarter later.
    witnesses = sorted(set(world.npcs_at(here) + world.npcs_at(to)) - {npc.id})
    npc.location = to
    event = world.log.append(
        Event(
            tick=world.clock.tick,
            type="move",
            actor=npc.id,
            location=to,
            data={"from": here, "to": to},
            witnesses=witnesses,
        )
    )
    return ActionResult(True, event=event)


def mentions(message: str, person_id: str, world) -> bool:
    """True if the message has the person's id or a word of their name (whole word, 3+ letters)."""
    words = [person_id, *(w for w in world.npcs[person_id].name.split() if len(w) >= 3)]
    return any(re.search(rf"\b{re.escape(w)}\b", message, re.I) for w in words)


def do_talk(world, intent: Intent) -> ActionResult:
    """Say something to someone in the same place. Others there overhear it."""
    npc = world.npcs[intent.actor]
    listener = world.npcs.get(intent.target or "")
    if listener is None:
        return reject(f"unknown npc {intent.target}")
    if listener.id == npc.id:
        return reject("cannot talk to yourself")
    # The dead are still in world.npcs, so the location check alone would let you
    # talk to a body. Refuse with a clear reason.
    if not listener.alive:
        return reject(f"{listener.id} is dead")
    if listener.location != npc.location:
        return reject(f"{listener.id} is not here")
    message = (intent.message or "").strip()
    if not message:
        return reject("message is empty")
    if len(message) > MAX_MESSAGE_CHARS:
        return reject(f"message is longer than {MAX_MESSAGE_CHARS} characters")

    # Everyone in the room hears it, including the listener. This is how rumours
    # will leak in week 3: the overhearers get the claim too.
    data = {"to": listener.id, "message": message}
    # The claim is only added when there is one, so plain talk logs exactly as before.
    # The engine never checks if a claim is true: lies are allowed.
    if intent.claim is not None:
        data["claim"] = intent.claim.model_dump()
    # Crude name check: catches a tag naming someone the words never mention.
    # It does not judge truth. The claim is still kept and the words never change;
    # the flag is only added when true, so normal claims log exactly as before.
    # Talking TO the subject counts as naming them: "you did it" needs no name (seen in
    # the week 5 smoke run, where Alice's "you" accusations to Victor were flagged).
    if (
        intent.claim is not None
        and intent.claim.subject != listener.id
        and not mentions(message, intent.claim.subject, world)
    ):
        data["claim"]["unverified"] = True
    witnesses = [n for n in world.npcs_at(npc.location) if n != npc.id]
    event = world.log.append(
        Event(
            tick=world.clock.tick,
            type="talk",
            actor=npc.id,
            location=npc.location,
            data=data,
            witnesses=witnesses,
        )
    )
    return ActionResult(True, event=event)


def do_look(world, intent: Intent) -> ActionResult:
    """See where you are, who is here and where you can go. Changes nothing."""
    here = world.npcs[intent.actor].location
    observation = {
        "location": here,
        "people": [n for n in world.npcs_at(here) if n != intent.actor],
        "exits": sorted(world.locations[here].links),
        # Dead NPCs are not "people". They show up here, so a body can be found.
        "bodies": world.bodies_at(here),
        # Only items on the ground. What people carry stays private until shown.
        "items": world.items_at(here, intent.actor),
        "holding": world.items_held(intent.actor),
        # People here who are held, so a villager can see custody with its own eyes.
        "held": [n for n in world.npcs_at(here) if world.npcs[n].held_by is not None],
    }
    return ActionResult(True, observation=observation)


# The full list of actions an agent may use. Add new actions here.
HANDLERS = {"move": do_move, "talk": do_talk, "look": do_look}

# Item actions live in their own file to keep this one small. They need the names
# above, so they are imported last.
from whisperwick.item_actions import do_drop, do_give, do_show, do_take, do_use  # noqa: E402

HANDLERS.update({"take": do_take, "drop": do_drop, "give": do_give, "show": do_show, "use": do_use})

# Custody actions, in their own file for the same reason.
from whisperwick.custody import do_arrest, do_release  # noqa: E402

HANDLERS.update({"arrest": do_arrest, "release": do_release})

# New villager actions use the same gate as the original handlers.
from whisperwick.gestures import do_gesture  # noqa: E402
from whisperwick.made_actions import do_make  # noqa: E402

HANDLERS.update({"gesture": do_gesture, "make": do_make})
