"""Player starting facts. Nothing here changes a villager's character or rules."""

import random
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from whisperwick.items import Item
from whisperwick.player import PLAYER_ID
from whisperwick.scenario import Scenario, check_references

ROLE_DIR = Path(__file__).resolve().parent.parent / "scenarios" / "roles"
ROLE_IDS = ("cousin", "peddler", "partner")


class StartingPlayer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    occupation: str
    title: str  # Player-only identity. Never copied to the world NPC.


class StartingMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    npc: str
    text: str


class StartingItem(Item):
    model_config = ConfigDict(extra="forbid")


class Role(BaseModel):
    # Reject extra keys rather than silently accepting a personality or rule.
    model_config = ConfigDict(extra="forbid")
    player: StartingPlayer
    items: list[StartingItem] = Field(default_factory=list)
    memory: StartingMemory | None = None

    @model_validator(mode="after")
    def player_items_only(self):
        if any(i.holder != PLAYER_ID or i.location is not None for i in self.items):
            raise ValueError("role items must start with the player")
        if self.memory and self.memory.npc == PLAYER_ID:
            raise ValueError("starting memory must belong to a villager")
        return self


def load_role(role_id: str) -> Role:
    if role_id not in ROLE_IDS:
        raise ValueError(f"unknown role {role_id!r}; choose cousin, peddler or partner")
    return Role.model_validate(yaml.safe_load((ROLE_DIR / f"{role_id}.yaml").read_text()))


def apply_role(sc: Scenario, role_id: str | None, seed: int | None = None) -> Scenario:
    """No role returns the original scenario, without even drawing a random number."""
    if role_id is None:
        return sc
    role = load_role(role_id)
    result = sc.model_copy(deep=True)
    player = next(n for n in result.npcs if n.id == PLAYER_ID)
    player.name, player.occupation = role.player.name, role.player.occupation
    ids = {i.id for i in result.items}
    for item in role.items:
        if item.id in ids:
            raise ValueError(f"role item already exists: {item.id}")
        ids.add(item.id)
        result.items.append(item.model_copy())
    if role.memory:
        result.evidence.setdefault(role.memory.npc, []).append(role.memory.text)
    if not sc.facts:
        raise ValueError("role needs a scenario facts pool")
    # A separate RNG leaves the engine's seeded action stream alone.
    result.private_fact = random.Random(sc.seed if seed is None else seed).choice(sc.facts)
    result.player_title = role.player.title
    result.role_id = role_id
    check_references(result)
    return result
