"""Small helpers for a long LLM run: where it saves, what it reports, the sidecar file.

The event log holds what happened. The sidecar JSON holds what the log cannot:
the model, the stats, what each NPC thought at night, and the ground truth.
"""

import json
from datetime import datetime
from pathlib import Path

from whisperwick.memory import Memories

FINAL_MEMORIES = 5  # how many of each NPC's last memories go in the sidecar


def default_db_path(scenario_name: str, now: datetime | None = None) -> str:
    """A fresh file per run, so two runs never mix. data/ is git-ignored."""
    now = now or datetime.now()
    return f"data/run-{scenario_name}-{now:%Y%m%d-%H%M%S}.db"


def sidecar_path(db: str | Path) -> Path:
    """The JSON file lives next to the db, with the same name."""
    return Path(db).with_suffix(".json")


def beliefs_path(db: str | Path) -> Path:
    """The belief log (JSON lines) lives next to the db too."""
    return Path(db).with_suffix(".beliefs.jsonl")


def rejection_rate(stats: dict) -> float:
    """Share of model calls the engine refused. 0 when there were no calls."""
    calls = stats.get("calls", 0)
    return stats.get("rejected", 0) / calls if calls else 0.0


def stats_line(stats: dict) -> str:
    """One readable line for the end of a run (and for the story)."""
    return (
        f"calls {stats.get('calls', 0)}, rejected {stats.get('rejected', 0)}, "
        f"errors {stats.get('errors', 0)}, thoughts {stats.get('thoughts', 0)}, "
        f"rejection rate {rejection_rate(stats):.1%}"
    )


def progress_line(clock_label: str, stats: dict, seconds: float) -> str:
    """One line per game hour, so a long run shows it is alive."""
    return (
        f"{clock_label}  calls {stats.get('calls', 0)}  rejected {stats.get('rejected', 0)}  "
        f"errors {stats.get('errors', 0)}  thoughts {stats.get('thoughts', 0)}  "
        f"{seconds:.0f}s"
    )


def sidecar_data(
    scenario_path: str | Path,
    model: str,
    minutes: int,
    stats: dict,
    secrets: dict,
    memories: Memories,
    player: str | None = None,
    belief_log: str | Path | None = None,
) -> dict:
    """Everything the story command needs besides the events. Ids only, no names."""
    reflections = {}
    final = {}
    for npc_id in sorted(memories):
        stream = memories[npc_id].memories
        reflections[npc_id] = [
            {"tick": m.tick, "text": m.text} for m in stream if m.kind == "reflection"
        ]
        final[npc_id] = [m.text for m in stream[-FINAL_MEMORIES:]]
    data = {
        "scenario": str(scenario_path),
        "model": model,
        "minutes": minutes,
        "stats": stats,
        "secrets": secrets,
        "reflections": reflections,
        "final_memories": final,
    }
    # Only play runs say who played: a script name, or "terminal".
    if player:
        data["player"] = player
    # Where this run's thoughts were saved, so reports can find them.
    if belief_log:
        data["belief_log"] = str(belief_log)
    return data


def write_sidecar(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))
