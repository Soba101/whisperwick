"""The body of `whisperwick replay`, kept out of cli.py. Read-only, no model.

World facts only: events and the scenario's names and map. The scenario secret and
the belief log are never read, except the optional private thoughts (text only,
shown behind a toggle that is off by default).
"""

import json
from pathlib import Path

from whisperwick import story
from whisperwick.llm_run import beliefs_path, sidecar_path
from whisperwick.replay_data import build_data
from whisperwick.replay_page import render_page
from whisperwick.scenario import load_scenario

DEFAULT_SCENARIO = Path("scenarios/murder_of_the_mayor.yaml")


def load_thoughts(db: Path) -> list[dict]:
    """Only tick, npc and the thinking text from each belief record. Nothing else."""
    path = beliefs_path(db)
    if not path.is_file():
        return []
    rows = (json.loads(x) for x in path.read_text().splitlines() if x.strip())
    return [
        {"tick": r["tick"], "npc": r["npc"], "text": r["thoughts"]}
        for r in rows
        if r.get("thoughts")
    ]


def run_label(db: Path) -> str:
    """e.g. 'none, qwen3.8:27b'. Falls back to the file name when there is no sidecar."""
    side = sidecar_path(db)
    if not side.is_file():
        return db.stem
    sidecar = json.loads(side.read_text())
    return ", ".join(str(sidecar[k]) for k in ("player", "model") if sidecar.get(k)) or db.stem


def replay_run(db: Path, out: Path | None = None, scenario: Path | None = None) -> Path:
    """Write the replay page and return its path. Raises FileNotFoundError for a missing file."""
    scenario = scenario or DEFAULT_SCENARIO
    for path in (db, scenario):
        if not path.is_file():
            raise FileNotFoundError(f"No such file: {path}")
    data = build_data(
        load_scenario(scenario), story.read_events(db), run_label(db), load_thoughts(db)
    )
    out = out or db.with_suffix(".replay.html")
    out.write_text(render_page(data))
    return out
