"""Actions: what an agent can *ask* the world to do.

An agent (stub now, LLM from week 2) returns an Intent.
The engine checks it and either applies it or rejects it with a reason.
Handlers here are the only code that changes NPC state.
"""

import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from whisperwick.events import Event

# Longest thing an NPC may say in one turn. Stops runaway LLM output later.
MAX_MESSAGE_CHARS = 500

# What a claim can say about a person. The one place to add a new kind.
CLAIM_KINDS = ("accuses", "defends")


class Claim(BaseModel):
    """A structured statement about one person, carried by a talk.

    Only claims (never free text) will change beliefs, so they must be well formed.
    The kind and subject are checked by the engine in claims.py, not here, so a bad
    one becomes a clear rejection reason instead of a parse error.
    """

    model_config = ConfigDict(extra="forbid")

    kind: str  # one of CLAIM_KINDS
    subject: str  # a person id, e.g. "npc_hal"


class Intent(BaseModel):
    """One proposed action. Week 2's JSON schema for the LLM is built from this."""

    # Reject unknown fields. A model inventing fields is a bug we want to see.
    model_config = ConfigDict(extra="forbid")

    actor: str  # who wants to act, e.g. "npc_bob"
    action: str  # "move" | "talk" | "look" | "take" | "drop" | "give" | "show"
    # A location id (move) or an npc id (talk, give, show).
    target: str | None = None
    message: str | None = None  # what to say (talk only)
    item: str | None = None  # an item id (take, drop, give, show)
    claim: Claim | None = None  # "accuses X" or "defends X" (talk only)


@dataclass
class ActionResult:
    """What the engine tells the agent after it tries something."""

    ok: bool
    reason: str = ""  # why it failed, in plain words (agents will read this)
    event: Event | None = None  # the event that was logged, if it changed the world
    observation: dict[str, Any] | None = None  # what the agent sees (look only)


def reject(reason: str) -> ActionResult:
    return ActionResult(False, reason)


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
    if intent.claim is not None and not mentions(message, intent.claim.subject, world):
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
        "items": world.items_at(here),
        "holding": world.items_held(intent.actor),
    }
    return ActionResult(True, observation=observation)


# The full list of actions an agent may use. Add new actions here.
HANDLERS = {"move": do_move, "talk": do_talk, "look": do_look}

# Item actions live in their own file to keep this one small. They need the names
# above, so they are imported last.
from whisperwick.item_actions import do_drop, do_give, do_show, do_take  # noqa: E402

HANDLERS.update({"take": do_take, "drop": do_drop, "give": do_give, "show": do_show})
