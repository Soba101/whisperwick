"""The body of `whisperwick outcome`, kept out of cli.py. World events only, no model."""

import json
from pathlib import Path

from whisperwick import outcome, story
from whisperwick.llm_run import sidecar_path
from whisperwick.scenario import load_scenario
from whisperwick.trace_command import load_names


def outcome_run(db: Path, scenario: Path | None = None) -> str:
    """Raises FileNotFoundError for a missing db. `scenario` turns on the secret line."""
    if not db.is_file():
        raise FileNotFoundError(f"No such file: {db}")
    side = sidecar_path(db)
    names = load_names(json.loads(side.read_text()) if side.is_file() else {})
    murderer = None
    if scenario:
        # Only read the secret when asked: it is not part of what the world did.
        murderer = load_scenario(scenario).secrets.get("murderer")
    return outcome.format_outcome(story.read_events(db), names, murderer)
