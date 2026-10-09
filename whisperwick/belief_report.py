"""Belief lines for reports (interview, compare, post-run). Plain text, no model.

Everything reads the belief log, so a run made before beliefs were logged
simply has no log, and every function here copes with that (None).
"""

from pathlib import Path

from whisperwick import trace
from whisperwick.belief_log import BeliefLog
from whisperwick.events import Event
from whisperwick.llm_run import beliefs_path

NO_LOG = "No belief log for this run (an older run?): nothing to show."


def find_log(db: Path, sidecar: dict) -> Path | None:
    """The belief file: the sidecar's 'belief_log' key, else <db>.beliefs.jsonl, else None."""
    for path in (sidecar.get("belief_log"), beliefs_path(db)):
        if path and Path(path).is_file():
            return Path(path)
    return None


def load_beliefs(db: Path, sidecar: dict) -> BeliefLog | None:
    path = find_log(db, sidecar)
    return BeliefLog.read(path) if path else None


def show(names: dict[str, str], thing_id: str) -> str:
    return names.get(thing_id, thing_id)


def suspect_cell(record: dict | None, names: dict[str, str]) -> str:
    """e.g. 'Victor (fairly sure)', from the villager's latest record."""
    if record is None:
        return "no thoughts logged"
    if record["suspect"] is None:
        return "nobody"
    return f"{show(names, record['suspect'])} ({record['sureness']})"


def interview_line(npc: str, answer: dict, log: BeliefLog, names: dict[str, str]) -> str:
    """e.g. 'Bob: told the interviewer Victor; privately suspects Victor (fairly sure)'."""
    told = show(names, answer["suspect"]) if answer["suspect"] else "no idea"
    record = log.latest(npc)
    private = "privately suspects " + suspect_cell(record, names)
    return f"  {show(names, npc)}: told the interviewer {told}; {private}"


def trust_line(log: BeliefLog, names: dict[str, str]) -> str:
    """e.g. 'Trust in the player: Alice high, Bob low, Hal not rated'."""
    parts = []
    for npc, rating in trace.trust_in_player(log).items():
        parts.append(f"{show(names, npc)} {rating['level'] if rating else 'not rated'}")
    return "Trust in the player: " + (", ".join(parts) or "-")


def claims_by_actor(events: list[Event], names: dict[str, str]) -> str:
    """e.g. 'Bob 1, Wren 2', or 'none'. Every talk that carried a claim, by who said it."""
    counts: dict[str, int] = {}
    for e in events:
        if e.type == "talk" and e.data.get("claim"):
            counts[show(names, e.actor)] = counts.get(show(names, e.actor), 0) + 1
    return ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none"


def compare_lines(log: BeliefLog | None, events: list[Event], names: dict[str, str]) -> list[str]:
    """One run's block for `compare`: latest suspects, trust in the player, counts."""
    if log is None:
        return ["    -"]
    people = sorted({r["npc"] for r in log.records})
    width = max((len(show(names, n)) for n in people), default=0) + 2
    lines = [
        f"    {show(names, n).ljust(width)}{suspect_cell(log.latest(n), names)}" for n in people
    ]
    own = trace.own_claims(events, log, names)
    hunches = sum(1 for r in log.records if r.get("hunch"))
    lines += [
        f"    {trust_line(log, names)}",
        f"    thoughts {len(log.records)}, hunches {hunches}, "
        f"claims: {claims_by_actor(events, names)}; own-claims (no source): {len(own)}",
    ]
    return lines
