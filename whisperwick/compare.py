"""Side-by-side report of several runs. Plain text, no model.

Everything except load_run is a pure function over plain dicts and events,
so it is easy to test. A run is {"name", "events", "sidecar"}. A missing
sidecar is {}, and anything it lacks shows as "-" (old runs have no interview).
"""

import json
from pathlib import Path

from whisperwick import story
from whisperwick.clock import Clock
from whisperwick.events import Event
from whisperwick.llm_run import rejection_rate, sidecar_path
from whisperwick.player import PLAYER_ID
from whisperwick.scenario import load_scenario

ITEM_EVENTS = ("take", "drop", "give", "show")
MAX_EVENT_LINES = 15  # per run, so three runs still fit on one screen
GAP = 2  # spaces after the longest cell in a column


def load_run(db: Path) -> dict:
    """Read one run's events and sidecar. A missing sidecar just means less data."""
    side = sidecar_path(db)
    sidecar = json.loads(side.read_text()) if side.is_file() else {}
    return {"name": db.name, "events": story.read_events(db), "sidecar": sidecar}


def load_names(runs: list[dict]) -> dict[str, str]:
    """id -> display name, from the first scenario file that still exists."""
    for run in runs:
        path = run["sidecar"].get("scenario")
        if path and Path(path).is_file():
            return story.names_from(load_scenario(path))
    return {}


def table(rows: list[list[str]], indent: str = "") -> list[str]:
    """Pad each column to its longest cell plus GAP, so long run names never collide."""
    widths = [max(len(r[i]) for r in rows) + GAP for i in range(len(rows[0]))]
    lines = ("".join(c.ljust(w) for c, w in zip(r, widths, strict=True)) for r in rows)
    return [(indent + line).rstrip() for line in lines]


def header_rows(runs: list[dict]) -> list[str]:
    """One row per run: db name, player script, model calls, rejection rate."""
    rows = [["Run", "Player", "Calls", "Rejected"]]
    for r in runs:
        s = r["sidecar"]
        stats = s.get("stats")
        calls = str(stats.get("calls", 0)) if stats else "-"
        rate = f"{rejection_rate(stats):.1%}" if stats else "-"
        rows.append([r["name"], s.get("player", "-"), calls, rate])
    return table(rows)


def suspect_of(run: dict, npc_id: str, names: dict[str, str]) -> str:
    """Display name of this NPC's suspect, or "-" (no answer, no idea, or old run)."""
    answer = run["sidecar"].get("interview", {}).get(npc_id)
    return story.show(names, answer["suspect"]) if answer and answer["suspect"] else "-"


def suspect_table(runs: list[dict], names: dict[str, str]) -> list[str]:
    """Rows = NPCs, columns = runs. NPCs are the union of everyone interviewed."""
    npcs = sorted({n for r in runs for n in r["sidecar"].get("interview", {})})
    grid = [["NPC", *(r["name"] for r in runs)]]
    for n in npcs:
        grid.append([story.show(names, n), *(suspect_of(r, n, names) for r in runs)])
    return ["Suspects:", *table(grid, "  ")] if npcs else ["Suspects: -"]


def vote_line(run: dict, names: dict[str, str]) -> str:
    """e.g. 'Victor 3, Hal 1, none 0'. Most votes first, ties by name."""
    answers = run["sidecar"].get("interview")
    if not answers:
        return f"{run['name']}: -"
    counts: dict[str, int] = {}
    for a in answers.values():
        if a["suspect"]:
            label = story.show(names, a["suspect"])
            counts[label] = counts.get(label, 0) + 1
    none = sum(1 for a in answers.values() if not a["suspect"])
    parts = [f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    return f"{run['name']}: " + ", ".join([*parts, f"none {none}"])


def item_line(run: dict, names: dict[str, str]) -> str:
    """Where each item ended up: a place name, or 'held by' a person."""
    items = run["sidecar"].get("items")
    if not items:
        return f"{run['name']}: -"
    parts = []
    for item_id, where in sorted(items.items()):
        place = where.get("location") or where.get("holder")
        label = story.show(names, place) if place else "-"
        held = "held by " if where.get("holder") else ""
        parts.append(f"{story.show(names, item_id)}: {held}{label}")
    return f"{run['name']}: " + "; ".join(parts)


def key_events(run: dict, names: dict[str, str]) -> list[str]:
    """Every player event and every item event, capped so the report stays short."""
    keep: list[Event] = [
        e for e in run["events"] if e.actor == PLAYER_ID or e.type in ITEM_EVENTS
    ]
    # story only gives HH:MM, so add the day here (d2 07:01).
    lines = [
        f"d{Clock(e.tick).day} {line}" for e in keep if (line := story.format_event(e, names))
    ]
    extra = len(lines) - MAX_EVENT_LINES
    lines = lines[:MAX_EVENT_LINES] + ([f"... and {extra} more"] if extra > 0 else [])
    return [f"{run['name']}:", *(f"  {x}" for x in lines or ["-"])]


def format_compare(runs: list[dict], names: dict[str, str]) -> str:
    """The whole report."""
    out = [*header_rows(runs), "", *suspect_table(runs, names), "", "Votes:"]
    out += [f"  {vote_line(r, names)}" for r in runs]
    out += ["", "Items at the end:", *(f"  {item_line(r, names)}" for r in runs)]
    out += ["", "Key events:"]
    for r in runs:
        out += key_events(r, names)
    return "\n".join(out)
