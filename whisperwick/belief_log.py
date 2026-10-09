"""The belief log: what each villager said it thought, and when.

Beliefs are model output, not world events, so they live here and not in the event log.
Each record is a plain dict (see thinking.py). The log only stores and looks things up:
it never decides what anyone believes. Agent side only, never part of World state.
"""

import json
from pathlib import Path


class BeliefLog:
    """Records in order. If a path is given, each one is also appended to it as a JSON line."""

    def __init__(self, path: str | Path | None = None):
        self.records: list[dict] = []
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, record: dict) -> None:
        self.records.append(record)
        if self.path:
            # One line per record, written at once, so a crashed run keeps what it had.
            with self.path.open("a") as f:
                f.write(json.dumps(record, sort_keys=True) + "\n")

    def latest(self, npc_id: str) -> dict | None:
        """The villager's newest record, or None if it has never thought."""
        mine = [r for r in self.records if r["npc"] == npc_id]
        return mine[-1] if mine else None

    def before(self, npc_id: str, event_id: int) -> dict | None:
        """The newest record made before this event happened (after_event < event_id).

        This answers: what did the villager think before it heard that?
        """
        mine = [r for r in self.records if r["npc"] == npc_id and r["after_event"] < event_id]
        return mine[-1] if mine else None

    @classmethod
    def read(cls, path: str | Path) -> "BeliefLog":
        """Load a finished run's file (for reports). Nothing is written back."""
        log = cls()
        for line in Path(path).read_text().splitlines():
            if line.strip():
                log.records.append(json.loads(line))
        return log
