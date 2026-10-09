"""The body of `whisperwick trace`, kept out of cli.py to keep that file small."""

import json
from pathlib import Path

from whisperwick import belief_report, story, trace


def trace_run(db: Path, subject: str, as_json: bool = False) -> str:
    """Rebuild the run's beliefs and trace one subject. No model is called.

    Raises FileNotFoundError for a missing db.
    """
    if not db.is_file():
        raise FileNotFoundError(f"No such file: {db}")
    state = belief_report.beliefs_for_run(db)
    result = trace.build_trace(state, subject)
    if as_json:
        return json.dumps(result, indent=2, sort_keys=True)
    names = story.names_from(belief_report.scenario_for_run(db))
    return trace.format_trace(result, names)
