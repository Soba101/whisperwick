"""Items: real objects with exactly one place.

An item is either on the ground at a location, or held by one living NPC.
Never both, never neither. Only the engine moves items (see item_actions.py).
"""

from pydantic import BaseModel


class Item(BaseModel):
    id: str  # stable id, e.g. "item_knife"
    name: str  # display name, for stories only
    description: str
    location: str | None = None  # location id, if it lies on the ground
    holder: str | None = None  # npc id, if someone carries it
