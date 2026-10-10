"""Code-only measures for one finished run. No model, nothing written.

Everything here reads a run as loaded by compare.load_run (events, sidecar, belief log).
Old runs lack the week 6 fields, so every measure copes with a missing key.
"""

import json
from pathlib import Path

from whisperwick import outcome
from whisperwick.clock import MINUTES_PER_DAY, Clock
from whisperwick.llm_run import rejection_rate
from whisperwick.player import PLAYER_ID
from whisperwick.scenario import load_scenario

AWAKE_HOURS = range(6, 22)  # 06:00 to 22:00, when villagers are expected to be active
DEFAULT_START = 8 * 60  # the scenario starts at 08:00 on day 1


def judge_path(db: Path) -> Path:
    """The judge's answers live next to the db, with the same name."""
    return Path(db).with_suffix(".judge.json")


def verdict(held: list[str], murderer: str | None) -> str:
    """right / wrong / mixed / nobody, judged against the scenario secret (not a world fact)."""
    if not held:
        return "nobody"
    if murderer is None:
        return "-"
    if murderer not in held:
        return "wrong"
    return "right" if held == [murderer] else "mixed"


def start_tick(sidecar: dict) -> int:
    """When the run began, from the scenario file if it still exists."""
    path = sidecar.get("scenario")
    if path and Path(path).is_file():
        return Clock.at(**load_scenario(path).start).tick
    return DEFAULT_START


def stalls(events, sidecar: dict) -> int:
    """Game hours between 06:00 and 22:00 in which no villager did anything at all."""
    npc_events = [e for e in events if e.actor != PLAYER_ID]
    start = start_tick(sidecar)
    end = start + sidecar.get("minutes", max((e.tick for e in events), default=start) - start)
    busy = {e.tick // 60 for e in npc_events}
    hours = range(start // 60, -(-end // 60))
    return sum(1 for h in hours if (h % 24) in AWAKE_HOURS and h not in busy)


def valid_sources(log) -> tuple[float | None, int]:
    """(share of suspect thoughts with at least one valid citation, number of those thoughts)."""
    with_suspect = [r for r in (log.records if log else []) if r.get("suspect")]
    if not with_suspect:
        return None, 0
    cited = sum(1 for r in with_suspect if r.get("because"))
    return cited / len(with_suspect), len(with_suspect)


def aim_counts(log) -> dict[str, int]:
    out = {"new": 0, "done": 0, "dropped": 0}
    for r in log.records if log else []:
        if r.get("aim_status") in out:
            out[r["aim_status"]] += 1
    return out


def load_judge(db: Path) -> dict | None:
    path = judge_path(db)
    return json.loads(path.read_text()) if path.is_file() else None


def measure(run: dict, db: Path) -> dict:
    """All the numbers for one run, as a flat dict that the tables read."""
    side, events, log = run["sidecar"], run["events"], run["beliefs"]
    stats = side.get("stats") or {}
    npc = [e for e in events if e.actor != PLAYER_ID]
    held = outcome.held_at_end(events)
    share, with_suspect = valid_sources(log)
    recalls = side.get("recalls")
    return {
        "name": run["name"],
        "script": side.get("player", "-"),
        "seed": side.get("seed"),
        "memory": bool(side.get("agent_memory", False)),  # older runs had no memory
        "days": side.get("minutes", 0) / MINUTES_PER_DAY,
        "held": held,
        "verdict": verdict(held, side.get("secrets", {}).get("murderer")),
        "calls": stats.get("calls", 0),
        "rejection": rejection_rate(stats),
        "talk_share": sum(e.type == "talk" for e in npc) / len(npc) if npc else 0.0,
        "recalls": recalls,
        "valid_share": share,
        "suspect_thoughts": with_suspect,
        "bad_citations": stats.get("bad_citations", 0),
        "aims": aim_counts(log),
        "arrests": sum(e.type == "arrest" for e in events),
        "releases": sum(e.type == "release" for e in events),
        "stalls": stalls(events, side),
        "judge": load_judge(db),
    }
