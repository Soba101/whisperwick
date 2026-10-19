"""An ending record lives outside the world and its event log."""

import json
from pathlib import Path

from whisperwick import ending, ending_scene, llm_run, story
from whisperwick.player import PLAYER_ID


class PlayerEnding:
    def __init__(self, sc):
        self.sc = sc
        self.events = None
        self.accusation = None  # None means not submitted; {target: None} means nobody.
        self.sidecar: Path | None = None

    def finish(self, events):
        self.events = list(events)

    def choose(self, target):
        ids = {n.id for n in self.sc.npcs if n.alive and n.id != PLAYER_ID}
        if self.events is None or self.accusation is not None:
            return False
        if target is not None and (not isinstance(target, str) or target not in ids):
            return False
        self.accusation = {"target": target}
        self.save()
        return True

    def save(self):
        # The run thread binds this only after its final sidecar has been written.
        if self.sidecar and self.accusation is not None:
            data = json.loads(self.sidecar.read_text())
            data["accusation"] = self.accusation
            llm_run.write_sidecar(self.sidecar, data)

    def snapshot(self, people):
        pending = self.events is not None and self.accusation is None
        return {
            "accusation_pending": pending,
            # Reveal fields share the same gate as the legacy text report.
            "ending_scene": ending_scene.scene(self.sc, self.events, self.accusation)
            if self.events is not None and not pending else None,
            # Only people already met appear before the truth is revealed.
            "accusation_choices": [{"id": p["id"], "name": p["name"]} for p in people],
            "ending": ending.report(self.events, story.names_from(self.sc), self.sc.secrets,
                                    self.sc.authority, self.accusation, self.sc.player_title)
            if self.events is not None and not pending else None,
        }
