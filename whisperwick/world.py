"""The world engine: the only code allowed to change world state.

Agents (later, LLMs) only *ask* to do things, by sending an Intent to
World.act(). The engine checks the request, applies it if it is legal,
and records an Event. This stops a model's hallucinations from ever
becoming "truth".
"""

import hashlib
import json
import random
from typing import Any

from pydantic import BaseModel, ValidationError

from whisperwick.actions import HANDLERS, ActionResult, Intent, reject
from whisperwick.clock import Clock
from whisperwick.events import Event, EventLog
from whisperwick.items import Item


class Location(BaseModel):
    id: str
    name: str
    links: list[str]  # locations you can walk to directly


class NPC(BaseModel):
    id: str
    name: str
    occupation: str
    location: str  # id of the location they are in right now
    # A dead NPC stays in the world as a body, but never acts, hears or is spoken to.
    alive: bool = True


class World:
    def __init__(
        self,
        locations: list[Location],
        npcs: list[NPC],
        clock: Clock,
        log: EventLog,
        seed: int = 0,
        items: list[Item] | None = None,
    ):
        # Dicts keyed by stable ID. Never key by display name.
        self.locations = {loc.id: loc for loc in locations}
        self.npcs = {npc.id: npc for npc in npcs}
        self.items = {item.id: item for item in items or []}
        self.clock = clock
        self.log = log
        # The world's own random generator. Anything random (the stub agent now,
        # e.g. theft success later) must use this, so it is saved with the world.
        self.rng = random.Random(seed)
        self._check_setup(locations, npcs, items or [])

    def _check_setup(self, locations: list[Location], npcs: list[NPC], items: list[Item]) -> None:
        """Refuse a broken scenario up front, instead of crashing mid-run.

        This raises on purpose: a bad scenario file is a bug in our data,
        not agent input.
        """
        if len(self.locations) != len(locations):
            raise ValueError("duplicate location ids")
        if len(self.npcs) != len(npcs):
            raise ValueError("duplicate npc ids")
        for loc in locations:
            for link in loc.links:
                if link not in self.locations:
                    raise ValueError(f"{loc.id} links to unknown location {link}")
        for npc in npcs:
            if npc.location not in self.locations:
                raise ValueError(f"{npc.id} starts in unknown location {npc.location}")
        if len(self.items) != len(items):
            raise ValueError("duplicate item ids")
        for item in items:
            # Exactly one of location / holder: an item is never in two places or none.
            if (item.location is None) == (item.holder is None):
                raise ValueError(f"{item.id} needs exactly one of location or holder")
            if item.location is not None and item.location not in self.locations:
                raise ValueError(f"{item.id} is in unknown location {item.location}")
            if item.holder is not None:
                if item.holder not in self.npcs:
                    raise ValueError(f"{item.id} is held by unknown npc {item.holder}")
                if not self.npcs[item.holder].alive:
                    raise ValueError(f"{item.id} is held by dead npc {item.holder}")

    def npcs_at(self, location_id: str) -> list[str]:
        """IDs of the LIVING at a location, sorted so results are deterministic.

        The dead are left out on purpose: they cannot witness, be talked to, or be seen
        as "people". Use bodies_at() to find them.
        """
        return sorted(n.id for n in self.npcs.values() if n.alive and n.location == location_id)

    def bodies_at(self, location_id: str) -> list[str]:
        """IDs of the dead at a location, sorted."""
        return sorted(
            n.id for n in self.npcs.values() if not n.alive and n.location == location_id
        )

    def items_at(self, location_id: str) -> list[str]:
        """IDs of items lying on the ground at a location, sorted."""
        return sorted(i.id for i in self.items.values() if i.location == location_id)

    def items_held(self, actor_id: str) -> list[str]:
        """IDs of items an NPC is carrying, sorted."""
        return sorted(i.id for i in self.items.values() if i.holder == actor_id)

    # ---- The one door agents use -------------------------------------------

    def act(self, intent: Intent | dict | Any) -> ActionResult:
        """Try one action. Bad input is rejected with a reason, never raised.

        Accepts an Intent or a plain dict (which is what an LLM's JSON becomes).
        """
        # Always re-validate, even an Intent object: one could have been changed
        # after it was built, or built without checks (model_construct).
        raw = intent.model_dump(warnings=False) if isinstance(intent, Intent) else intent
        try:
            intent = Intent.model_validate(raw)
        except ValidationError as e:
            first = e.errors()[0]
            where = ".".join(str(p) for p in first["loc"]) or "intent"
            return reject(f"malformed intent ({where}: {first['msg']})")
        if intent.actor not in self.npcs:
            return reject(f"unknown npc {intent.actor}")
        # The dead cannot act. Checked before the handler so no action can slip through.
        if not self.npcs[intent.actor].alive:
            return reject(f"{intent.actor} is dead")
        handler = HANDLERS.get(intent.action)
        if handler is None:
            return reject(f"unknown action {intent.action}")
        return handler(self, intent)

    def move(self, npc_id: str, to: str) -> ActionResult:
        """Shortcut for a move intent. Handy in tests and scripts."""
        return self.act(Intent(actor=npc_id, action="move", target=to))

    def step(self, intents: list[Intent | dict | Any]) -> list[ActionResult]:
        """One tick: apply this minute's intents, then move the clock on.

        Intents run in actor-id order, so the result never depends on which
        agent happened to answer first. Junk items are not inspected here:
        they sort by their text form and act() rejects them.
        """

        def actor_key(item: Any) -> str:
            actor = item.get("actor") if isinstance(item, dict) else getattr(item, "actor", "")
            return str(actor)

        results = [self.act(i) for i in sorted(intents, key=actor_key)]
        self.clock.advance()
        return results

    # ---- Save, load and fingerprint ----------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """The full world state as plain data. Sorted, so the same world = same dict."""
        return {
            "tick": self.clock.tick,
            "locations": [self.locations[k].model_dump() for k in sorted(self.locations)],
            "npcs": [self.npcs[k].model_dump() for k in sorted(self.npcs)],
            "items": [self.items[k].model_dump() for k in sorted(self.items)],
            "events": [e.model_dump() for e in self.log.all()],
            # Saving the generator's exact position makes resumed runs identical.
            "rng": self.rng.getstate(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], db_path: str = ":memory:") -> "World":
        """Rebuild a world from to_dict() output. Used for save/load."""
        log = EventLog(db_path)
        for raw in data["events"]:
            # Re-appending in order gives the same ids (1, 2, 3, ...) as before.
            log.append(Event.model_validate({**raw, "id": None}))
        world = cls(
            [Location.model_validate(x) for x in data["locations"]],
            [NPC.model_validate(x) for x in data["npcs"]],
            Clock(data["tick"]),
            log,
            # Older saves have no items key.
            items=[Item.model_validate(x) for x in data.get("items", [])],
        )
        # JSON turns the state's tuples into lists; setstate needs tuples back.
        version, internal, gauss = data["rng"]
        world.rng.setstate((version, tuple(internal), gauss))
        return world

    def state_hash(self) -> str:
        """A short fingerprint of the whole world. Equal worlds = equal hashes."""
        text = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(text.encode()).hexdigest()[:16]
