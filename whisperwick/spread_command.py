"""Read-only command for following a subject through a finished run."""

import json
from pathlib import Path
from typing import Annotated

import typer

from whisperwick import belief_report, spread, story
from whisperwick.llm_run import sidecar_path


def spread_run(db: Path, subject: str) -> str:
    """Use the same belief-file lookup as trace, including runs without a sidecar."""
    if not db.is_file():
        raise FileNotFoundError(f"No such file: {db}")
    side = sidecar_path(db)
    sidecar = json.loads(side.read_text()) if side.is_file() else {}
    log = belief_report.load_beliefs(db, sidecar)
    # Stable IDs keep receipts unambiguous even when the scenario has moved.
    return spread.render(story.read_events(db), log, subject)


def spread_command(
    db: Annotated[Path, typer.Argument(help="Event log from a finished run.")],
    subject: Annotated[str, typer.Argument(help="Subject NPC id, e.g. npc_victor.")],
) -> None:
    """Who told whom about SUBJECT, cited memories and custody. No model is called."""
    try:
        typer.echo(spread_run(db, subject))
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
