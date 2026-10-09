"""Load a scenario YAML file into a ready-to-run World."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from whisperwick.clock import Clock
from whisperwick.events import EventLog
from whisperwick.items import Item
from whisperwick.world import NPC, Location, World


class StartingBelief(BaseModel):
    """One starting belief: "I think <subject> killed the mayor", with a short reason."""

    subject: str  # a person id
    confidence: float  # 0..1
    note: str  # why, e.g. "saw Victor hurrying from the Town Hall"

    @field_validator("confidence")
    @classmethod
    def _in_range(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return v


class Scenario(BaseModel):
    name: str
    seed: int
    start: dict[str, int]  # {"day": 1, "hour": 8}
    locations: list[Location]
    npcs: list[NPC]
    items: list[Item] = Field(default_factory=list)  # real objects, optional
    secrets: dict[str, Any] = Field(default_factory=dict)  # ground truth, engine-only
    # Private starting memories: npc id -> lines only that NPC knows at the start.
    evidence: dict[str, list[str]] = Field(default_factory=dict)
    # Week 4 (all optional, so old scenarios still load):
    # How much people trust each other: {default: 0.5, player: 0.3}.
    trust: dict[str, float] = Field(default_factory=dict)
    # Telling items: item id -> the person it points to when shown or given.
    clues: dict[str, str] = Field(default_factory=dict)
    # Starting beliefs: npc id -> list of beliefs held at the start.
    beliefs: dict[str, list[StartingBelief]] = Field(default_factory=dict)
    # One-sentence goals: npc id -> goal. Used by the prompt (task 3).
    goals: dict[str, str] = Field(default_factory=dict)


def load_scenario(path: str | Path) -> Scenario:
    """Read and validate a scenario file. Bad files fail loudly here."""
    with open(path) as f:
        return Scenario.model_validate(yaml.safe_load(f))


def check_references(scenario: Scenario) -> None:
    """Refuse secrets or evidence that point at ids that do not exist.

    A typo like npc_victer would silently make a clue useless, so fail loudly.
    """
    npc_ids = {n.id for n in scenario.npcs}
    loc_ids = {loc.id for loc in scenario.locations}
    for key, value in scenario.secrets.items():
        if isinstance(value, str) and value.startswith("npc_") and value not in npc_ids:
            raise ValueError(f"secret {key} names unknown npc {value}")
        if isinstance(value, str) and value.startswith("loc_") and value not in loc_ids:
            raise ValueError(f"secret {key} names unknown location {value}")
    for item in scenario.items:
        if item.location is not None and item.location not in loc_ids:
            raise ValueError(f"item {item.id} is in unknown location {item.location}")
        if item.holder is not None and item.holder not in npc_ids:
            raise ValueError(f"item {item.id} is held by unknown npc {item.holder}")
    for npc_id in scenario.evidence:
        if npc_id not in npc_ids:
            raise ValueError(f"evidence given to unknown npc {npc_id}")

    # The week 4 sections: every id must be real, and numbers must make sense.
    for key, value in scenario.trust.items():
        if key not in ("default", "player"):
            raise ValueError(f"trust has unknown key {key}")
        if not 0 <= value <= 1:
            raise ValueError(f"trust {key} must be between 0 and 1")
    item_ids = {i.id for i in scenario.items}
    for item_id, person in scenario.clues.items():
        if item_id not in item_ids:
            raise ValueError(f"clue names unknown item {item_id}")
        if person not in npc_ids:
            raise ValueError(f"clue {item_id} points to unknown npc {person}")
    for npc_id, beliefs in scenario.beliefs.items():
        if npc_id not in npc_ids:
            raise ValueError(f"belief given to unknown npc {npc_id}")
        for belief in beliefs:
            if belief.subject not in npc_ids:
                raise ValueError(f"belief of {npc_id} names unknown npc {belief.subject}")
    for npc_id in scenario.goals:
        if npc_id not in npc_ids:
            raise ValueError(f"goal given to unknown npc {npc_id}")


def build_world(scenario: Scenario, db_path: str = ":memory:", seed: int | None = None) -> World:
    """Turn a scenario into a World with a fresh clock and event log.

    The seed defaults to the scenario's own seed.
    """
    clock = Clock.at(scenario.start["day"], scenario.start["hour"])
    # Copy the NPCs so running a world never changes the scenario object.
    npcs = [npc.model_copy() for npc in scenario.npcs]
    check_references(scenario)
    seed = scenario.seed if seed is None else seed
    # Copy items too, for the same reason.
    items = [item.model_copy() for item in scenario.items]
    return World(scenario.locations, npcs, clock, EventLog(db_path), seed=seed, items=items)
