"""The agent log: what villagers privately did with their memory (recall searches).

Like the belief log it is model-side data, not world events. Records are plain dicts.
If a path is given each one is also appended as a JSON line, so a crashed run keeps them.
"""

import json
from pathlib import Path


class AgentLog:
    def __init__(self, path: str | Path | None = None):
        self.records: list[dict] = []
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, record: dict) -> None:
        self.records.append(record)
        if self.path:
            with self.path.open("a") as f:
                f.write(json.dumps(record, sort_keys=True) + "\n")

    def recall(self, tick: int, npc: str, when: str, words: str, found: list[str]) -> None:
        """when is "act" or "think"."""
        self.add({"tick": tick, "npc": npc, "kind": "recall", "when": when,
                  "words": words, "found": found})  # fmt: skip

    def recall_counts(self) -> dict[str, int]:
        counts = {"act": 0, "think": 0}
        for r in self.records:
            if r.get("kind") == "recall":
                counts[r["when"]] += 1
        return counts


def sidecar_part(agent_memory: bool, log: AgentLog, notebooks) -> dict:
    """What the sidecar says about villager memory: the switch, recall counts, final notebooks."""
    part: dict = {"agent_memory": agent_memory}
    if agent_memory:
        part["recalls"] = log.recall_counts()
        part["notebooks"] = notebooks.to_dict()
    return part
