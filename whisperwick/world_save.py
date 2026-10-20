"""Save and load world facts. Made definitions are rebuilt from the event log."""

import hashlib
import json
from typing import Any, Self

from whisperwick.clock import Clock
from whisperwick.events import Event, EventLog
from whisperwick.items import Item


class WorldSave:
    # ---- Save, load and fingerprint ----------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """The full world state as plain data. Sorted, so the same world = same dict."""
        return {
            "tick": self.clock.tick,
            "locations": [self.locations[k].model_dump() for k in sorted(self.locations)],
            "npcs": [self.npcs[k].model_dump() for k in sorted(self.npcs)],
            "items": [self.items[k].saved() for k in sorted(self.items)],
            "authority": sorted(self.authority),
            "events": [e.model_dump() for e in self.log.all()],
            # Saving the generator's exact position makes resumed runs identical.
            "rng": self.rng.getstate(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], db_path: str = ":memory:") -> Self:
        """Rebuild a world from to_dict() output. Used for save/load."""
        from whisperwick.world import NPC, Location

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
            authority=data.get("authority", []),
        )
        # JSON turns the state's tuples into lists; setstate needs tuples back.
        version, internal, gauss = data["rng"]
        world.rng.setstate((version, tuple(internal), gauss))
        return world

    def state_hash(self) -> str:
        """A short fingerprint of the whole world. Equal worlds = equal hashes."""
        text = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(text.encode()).hexdigest()[:16]
