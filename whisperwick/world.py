"""The world engine: the only code allowed to change world state.

Agents (later, LLMs) only *ask* to do things, by sending an Intent to
World.act(). The engine checks the request, applies it if it is legal,
and records an Event. This stops a model's hallucinations from ever
becoming "truth".
"""

import random
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ValidationError

from whisperwick.actions import HANDLERS, ActionResult, Intent, reject
from whisperwick.claims import claim_problem
from whisperwick.clock import Clock
from whisperwick.custody import held_problem
from whisperwick.events import EventLog
from whisperwick.items import Item, check_items
from whisperwick.world_save import WorldSave


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
    # Who is holding this NPC in custody (an authority's id), or None if free.
    # World state, so it is saved and part of the state hash.
    held_by: str | None = None


class World(WorldSave):
    def __init__(
        self,
        locations: list[Location],
        npcs: list[NPC],
        clock: Clock,
        log: EventLog,
        seed: int = 0,
        items: list[Item] | None = None,
        authority: list[str] | None = None,
    ):
        # Dicts keyed by stable ID. Never key by display name.
        self.locations = {loc.id: loc for loc in locations}
        self.npcs = {npc.id: npc for npc in npcs}
        self.items = {item.id: item for item in items or []}
        # Ids of NPCs who may arrest and release. A fact about the world, like who
        # holds an item. The world never picks who gets arrested; it only allows it.
        self.authority = list(authority or [])
        self.clock = clock
        self.log = log
        # The log owns definitions. Wishes are diagnostics, never world facts.
        from whisperwick.made_actions import rebuild

        self.made_actions = rebuild(log.all())
        self.wishes = []
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
        for who in self.authority:
            if who not in self.npcs:
                raise ValueError(f"authority {who} is not a known npc")
        for npc in npcs:
            if npc.held_by is not None and npc.held_by not in self.authority:
                raise ValueError(f"{npc.id} is held by {npc.held_by}, who has no authority")
        check_items(items, self.locations, self.npcs, self.log)

    def npcs_at(self, location_id: str) -> list[str]:
        """IDs of the LIVING at a location, sorted so results are deterministic.

        The dead are left out on purpose: they cannot witness, be talked to, or be seen
        as "people". Use bodies_at() to find them.
        """
        return sorted(n.id for n in self.npcs.values() if n.alive and n.location == location_id)

    def bodies_at(self, location_id: str) -> list[str]:
        """IDs of the dead at a location, sorted."""
        return sorted(n.id for n in self.npcs.values() if not n.alive and n.location == location_id)

    def items_at(self, location_id: str, viewer: str | None = None) -> list[str]:
        """IDs of items lying on the ground at a location, sorted."""
        return sorted(i.id for i in self.items.values()
                      if i.location == location_id and i.visible_to(viewer))

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
        if isinstance(raw, dict):
            actor, action = raw.get("actor"), raw.get("action")
            if (isinstance(actor, str) and actor != "player" and actor in self.npcs
                    and self.npcs[actor].alive and isinstance(action, str)
                    and action not in HANDLERS and action not in self.made_actions.get(actor, {})):
                self.wishes.append({"tick": self.clock.tick, "actor": actor,
                                    "action": action, "intent": deepcopy(raw)})
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
        if handler is None and intent.action in self.made_actions.get(intent.actor, {}):
            from whisperwick.made_actions import do_made

            handler = do_made
        if handler is None:
            return reject(f"unknown action {intent.action}")
        # A claim must be well formed and only ever rides on a talk. Checked here, before
        # any handler runs, so a bad claim can never change anything.
        problem = claim_problem(self, intent)
        if problem:
            return reject(problem)
        # Custody: a held person cannot move, take, drop or give. One check, here,
        # so no handler can forget it.
        problem = held_problem(self, intent)
        if problem:
            return reject(problem)
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
