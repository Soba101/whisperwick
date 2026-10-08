"""The event log: the single source of truth.

Every change to the world is recorded here as an Event.
Later, perception, memory and rumours are all built by reading events.
We store events in SQLite so a run can be inspected after it ends.
"""

import json
import sqlite3
from typing import Any

from pydantic import BaseModel, Field


class Event(BaseModel):
    """One thing that happened. Fields use IDs, never display names."""

    id: int | None = None  # set by the log when the event is stored
    tick: int  # game minute when it happened
    type: str  # e.g. "move", later "talk", "steal"
    actor: str  # who did it, e.g. "npc_bob"
    location: str  # where it happened
    data: dict[str, Any] = Field(default_factory=dict)  # type-specific details
    witnesses: list[str] = Field(default_factory=list)  # who could see it (decided in code)


class EventLog:
    """Append-only store for events. Nothing is ever edited or deleted."""

    def __init__(self, path: str = ":memory:"):
        # ":memory:" keeps tests fast. Pass a file path to keep a run.
        self.db = sqlite3.connect(path)
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tick INTEGER NOT NULL,
                type TEXT NOT NULL,
                actor TEXT NOT NULL,
                location TEXT NOT NULL,
                data TEXT NOT NULL,       -- JSON
                witnesses TEXT NOT NULL   -- JSON list of NPC ids
            )"""
        )

    def append(self, event: Event) -> Event:
        """Store an event and return it with its new id."""
        cur = self.db.execute(
            "INSERT INTO events (tick, type, actor, location, data, witnesses)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.tick,
                event.type,
                event.actor,
                event.location,
                json.dumps(event.data, sort_keys=True),
                json.dumps(event.witnesses),
            ),
        )
        self.db.commit()
        return event.model_copy(update={"id": cur.lastrowid})

    def all(self) -> list[Event]:
        """Every event, oldest first."""
        rows = self.db.execute(
            "SELECT id, tick, type, actor, location, data, witnesses FROM events ORDER BY id"
        )
        return [
            Event(
                id=r[0],
                tick=r[1],
                type=r[2],
                actor=r[3],
                location=r[4],
                data=json.loads(r[5]),
                witnesses=json.loads(r[6]),
            )
            for r in rows
        ]
