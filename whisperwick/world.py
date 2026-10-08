"""The world engine: the only code allowed to change world state.

Agents (later, LLMs) only *ask* to do things. The engine checks the request,
applies it if it is legal, and records an Event. This stops a model's
hallucinations from ever becoming "truth".
"""

from dataclasses import dataclass

from pydantic import BaseModel

from whisperwick.clock import Clock
from whisperwick.events import Event, EventLog


class Location(BaseModel):
    id: str
    name: str
    links: list[str]  # locations you can walk to directly


class NPC(BaseModel):
    id: str
    name: str
    occupation: str
    location: str  # id of the location they are in right now


@dataclass
class ActionResult:
    """What the engine tells the agent after it tries something."""

    ok: bool
    reason: str = ""  # why it failed, in plain words (agents will read this)
    event: Event | None = None  # the event that was logged, if it worked


class World:
    def __init__(self, locations: list[Location], npcs: list[NPC], clock: Clock, log: EventLog):
        # Dicts keyed by stable ID. Never key by display name.
        self.locations = {loc.id: loc for loc in locations}
        self.npcs = {npc.id: npc for npc in npcs}
        self.clock = clock
        self.log = log

    def npcs_at(self, location_id: str) -> list[str]:
        """IDs of everyone at a location, sorted so results are deterministic."""
        return sorted(n.id for n in self.npcs.values() if n.location == location_id)

    def move(self, npc_id: str, to: str) -> ActionResult:
        """Walk an NPC to a neighbouring location.

        Rules (all checked here, never by an LLM):
        - the NPC and the target must exist
        - the target must be linked to where the NPC is now (no teleporting)
        """
        npc = self.npcs.get(npc_id)
        if npc is None:
            return ActionResult(False, f"unknown npc {npc_id}")
        if to not in self.locations:
            return ActionResult(False, f"unknown location {to}")
        here = npc.location
        if to not in self.locations[here].links:
            return ActionResult(False, f"{to} is not reachable from {here}")

        # Witnesses = anyone at the start or the end of the walk, except the walker.
        # This is a simple first rule; perception gets smarter later.
        witnesses = sorted(set(self.npcs_at(here) + self.npcs_at(to)) - {npc_id})

        npc.location = to
        event = self.log.append(
            Event(
                tick=self.clock.tick,
                type="move",
                actor=npc_id,
                location=to,
                data={"from": here, "to": to},
                witnesses=witnesses,
            )
        )
        return ActionResult(True, event=event)
