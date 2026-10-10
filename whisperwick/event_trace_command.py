"""The body of `whisperwick trace DB --event N`, kept out of cli.py. No model is called."""

import json
from pathlib import Path

from whisperwick import belief_report, event_trace, story, trace_command
from whisperwick.llm_run import sidecar_path
from whisperwick.trace_command import load_names


def trace_event_run(db: Path, event_id: int) -> str:
    """Raises FileNotFoundError (no db) or ValueError (no such event)."""
    if not db.is_file():
        raise FileNotFoundError(f"No such file: {db}")
    side = sidecar_path(db)
    sidecar = json.loads(side.read_text()) if side.is_file() else {}
    log = belief_report.load_beliefs(db, sidecar)
    return event_trace.explain(story.read_events(db), log, event_id, load_names(sidecar))


def trace_any(db: Path, subject: str | None, event_id: int | None, as_json: bool) -> str:
    """One door for `trace`: exactly one of SUBJECT or --event. Raises ValueError otherwise."""
    if (subject is None) == (event_id is None):
        raise ValueError("Give exactly one of SUBJECT or --event N.")
    if event_id is not None:
        return trace_event_run(db, event_id)
    return trace_command.trace_run(db, subject, as_json)
