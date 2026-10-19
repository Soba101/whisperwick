"""Items: real objects with engine-owned presence.

An item is either on the ground at a location, or held by one living NPC.
Never both. A used consumable has neither, but keeps its record for logs.
Only the engine moves items (see item_actions.py).
"""

from pydantic import BaseModel


class Item(BaseModel):
    id: str  # stable id, e.g. "item_knife"
    name: str  # display name, for stories only
    description: str
    location: str | None = None  # location id, if it lies on the ground
    holder: str | None = None  # npc id, if someone carries it
    consumable: bool = False  # the engine may remove it through use
    use_verb: str | None = None  # scenario wording, e.g. "drinks"; never model output


def check_items(items, locations, npcs, log) -> None:
    """Reject broken placement, allowing logged consumables to stay absent on load."""
    if len({item.id for item in items}) != len(items):
        raise ValueError("duplicate item ids")
    # A logged use explains an absent consumable when loading a saved world.
    used_ids = {e.data.get("item") for e in log.all() if e.type == "use"}
    for item in items:
        used = item.consumable and item.id in used_ids
        # Exactly one of location / holder: an item is never in two places or none.
        # Exception: a used-up consumable keeps only its record (no place at all).
        if (item.location is None) == (item.holder is None) and not (
            used and item.location is None and item.holder is None
        ):
            raise ValueError(f"{item.id} needs exactly one of location or holder")
        if item.location is not None and item.location not in locations:
            raise ValueError(f"{item.id} is in unknown location {item.location}")
        if item.holder is not None:
            if item.holder not in npcs:
                raise ValueError(f"{item.id} is held by unknown npc {item.holder}")
            if not npcs[item.holder].alive:
                raise ValueError(f"{item.id} is held by dead npc {item.holder}")
