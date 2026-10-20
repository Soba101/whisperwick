"""Unknown villager actions are wishes for future physics, outside the event log."""

import json
from collections import Counter
from pathlib import Path

import typer

from whisperwick.llm_run import sidecar_path


def counts(wishes):
    """Sort by stable action name so reports are repeatable."""
    return dict(sorted(Counter(w["action"] for w in wishes).items()))


def wishes(db: Path):
    """Print counts by action name from a run's sidecar."""
    path = sidecar_path(db)
    data = json.loads(path.read_text()) if path.is_file() else {}
    found = counts(data.get("wishes", []))
    for action, count in found.items():
        typer.echo(f"{action}: {count}")
    if not found:
        typer.echo("No wishes.")
