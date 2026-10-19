"""The body of `whisperwick outcome`, kept out of cli.py. Saved facts and truth, no model."""

import json
from pathlib import Path

from whisperwick import ending, outcome, story
from whisperwick.llm_run import sidecar_path
from whisperwick.scenario import load_scenario
from whisperwick.trace_command import load_names


def outcome_run(db: Path, scenario: Path | None = None) -> str:
    """Raises FileNotFoundError for a missing db. `scenario` supplies truth for old runs."""
    if not db.is_file():
        raise FileNotFoundError(f"No such file: {db}")
    side = sidecar_path(db)
    data = json.loads(side.read_text()) if side.is_file() else {}
    names = load_names(data)
    # Saved metadata keeps endings usable even after the scenario file is gone.
    saved_path = data.get("scenario")
    source = scenario or (Path(saved_path) if saved_path and Path(saved_path).is_file() else None)
    sc = load_scenario(source) if source else None
    murderer = sc.secrets.get("murderer") if scenario else None
    secrets = sc.secrets if scenario else data.get("secrets", {})
    authority = data.get("authority", sc.authority if sc else [])
    if secrets:
        text = ending.report(story.read_events(db), names, secrets,
                             sc.authority if scenario else authority, data.get("accusation"),
                             data.get("player_title"))
        # Preserve the explicit secret line used by older command consumers.
        if scenario and murderer:
            text += f"\nScenario secret: murderer = {murderer}"
        return text
    return outcome.format_outcome(story.read_events(db), names, murderer)
