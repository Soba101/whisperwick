"""The body of `whisperwick trace`, kept out of cli.py to keep that file small.

Reads the event log and the belief log. No model is called, nothing is written.
"""

import json
from pathlib import Path

from whisperwick import belief_report, story, trace
from whisperwick.llm_run import sidecar_path
from whisperwick.scenario import load_scenario

THOUGHTS_SHOWN = 120  # a trace is a map, not a diary: trim long thoughts


def load_names(sidecar: dict) -> dict[str, str]:
    """id -> display name from the run's scenario, if it still exists. Else ids are shown."""
    path = sidecar.get("scenario")
    return story.names_from(load_scenario(path)) if path and Path(path).is_file() else {}


def render_steps(steps: list[dict], indent: str) -> list[str]:
    """Each step on its own line; what is behind it is indented one level deeper."""
    lines = []
    for s in steps:
        lines.append(f"{indent}- {s['text']}")
        lines += render_steps(s["then"], indent + "    ")
    return lines


def render_believer(b: dict) -> list[str]:
    """The believer's own words first, then the chain behind them."""
    what = f" of {b['of_what']}" if b["of_what"] else ""
    thoughts = b["thoughts"]
    if len(thoughts) > THOUGHTS_SHOWN:
        thoughts = thoughts[: THOUGHTS_SHOWN - 3] + "..."
    head = [f"{b['name']}: {b['sureness']}{what}", f'  thinks: "{thoughts}"']
    if b.get("will_accuse"):
        head.append(f"  meant to accuse: {b['will_accuse']}")
    return [*head, *render_steps(b["chain"], "  ")]


def render(result: dict, names: dict[str, str]) -> str:
    subject = belief_report.show(names, result["subject"])
    out = [f"Who suspects {subject} ({result['subject']})?"]
    if not result["believers"]:
        out.append("  Nobody (by their latest thought).")
    for b in result["believers"]:
        out += render_believer(b)
    if result["used_to_suspect"]:
        out += ["", "Used to suspect (no longer):"]
        for b in result["used_to_suspect"]:
            out += render_believer(b)
    out += ["", "Trust in the player:"]
    for npc, rating in result["trust_in_player"].items():
        said = f"{rating['level']}: {rating['why']}" if rating else "not rated"
        out.append(f"  {belief_report.show(names, npc)}: {said}")
    return "\n".join(out)


def trace_run(db: Path, subject: str, as_json: bool = False) -> str:
    """Raises FileNotFoundError for a missing db. An old run (no belief log) gets a message."""
    if not db.is_file():
        raise FileNotFoundError(f"No such file: {db}")
    side = sidecar_path(db)
    sidecar = json.loads(side.read_text()) if side.is_file() else {}
    log = belief_report.load_beliefs(db, sidecar)
    if log is None:
        # --json still prints valid JSON, so a script calling it does not break.
        return (
            json.dumps({"subject": subject, "message": belief_report.NO_LOG})
            if as_json
            else belief_report.NO_LOG
        )
    names = load_names(sidecar)
    result = trace.trace(story.read_events(db), log, subject, names)
    return json.dumps(result, indent=2) if as_json else render(result, names)
