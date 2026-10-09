"""Load a scenario YAML file into a ready-to-run World."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from whisperwick.clock import Clock
from whisperwick.events import EventLog
from whisperwick.world import NPC, Location, World


class Scenario(BaseModel):
    name: str
    seed: int
    start: dict[str, int]  # {"day": 1, "hour": 8}
    locations: list[Location]
    npcs: list[NPC]
    secrets: dict[str, Any] = Field(default_factory=dict)  # ground truth, engine-only


def load_scenario(path: str | Path) -> Scenario:
    """Read and validate a scenario file. Bad files fail loudly here."""
    with open(path) as f:
        return Scenario.model_validate(yaml.safe_load(f))


def build_world(scenario: Scenario, db_path: str = ":memory:", seed: int | None = None) -> World:
    """Turn a scenario into a World with a fresh clock and event log.

    The seed defaults to the scenario's own seed.
    """
    clock = Clock.at(scenario.start["day"], scenario.start["hour"])
    # Copy the NPCs so running a world never changes the scenario object.
    npcs = [npc.model_copy() for npc in scenario.npcs]
    seed = scenario.seed if seed is None else seed
    return World(scenario.locations, npcs, clock, EventLog(db_path), seed=seed)
