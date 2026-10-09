"""Turn an event log into a readable transcript. Code only, no model.

Everything here is a pure function over events and plain dicts, so it is easy to test.
Names are looked up from ids at the very end, only for display.
"""

from pathlib import Path

from whisperwick.clock import MINUTES_PER_DAY, Clock
from whisperwick.events import Event, EventLog
from whisperwick.llm_run import stats_line
from whisperwick.scenario import Scenario

PLACE_WIDTH = 12  # keeps the speaker column lined up in the transcript


def read_events(db_path: str | Path) -> list[Event]:
    """Read every event from an existing db, without ever writing to it.

    EventLog.read() opens the file read-only (see its comment for why).
    """
    return EventLog.read(str(db_path))


def names_from(scenario: Scenario | None) -> dict[str, str]:
    """id -> display name for every NPC and place. Empty means: show the ids."""
    if scenario is None:
        return {}
    return {x.id: x.name for x in [*scenario.npcs, *scenario.locations]}


def show(names: dict[str, str], thing_id: str) -> str:
    """A display name if we know one, else the id itself."""
    return names.get(thing_id, thing_id)


def hhmm(tick: int) -> str:
    """Clock time only, e.g. '08:05'. The day has its own header."""
    return Clock(tick).label().split(" ", 2)[2]


def format_event(e: Event, names: dict[str, str]) -> str | None:
    """One line for a talk or a move. Other events (like look) are left out."""
    if e.type == "talk":
        place = show(names, e.location).ljust(PLACE_WIDTH)
        who, to = show(names, e.actor), show(names, e.data["to"])
        return f'{hhmm(e.tick)}  {place} {who} -> {to}: "{e.data["message"]}"'
    if e.type == "move":
        src, dst = show(names, e.data["from"]), show(names, e.data["to"])
        return f"{hhmm(e.tick)}  {show(names, e.actor)} walks {src} -> {dst}"
    return None


def night_thoughts(reflections: dict, day: int, names: dict[str, str]) -> list[str]:
    """Each NPC's reflections made on this day. Sorted by id so output is stable."""
    lines = []
    for npc_id in sorted(reflections):
        for r in reflections[npc_id]:
            if r["tick"] // MINUTES_PER_DAY + 1 == day:
                lines.append(f'  {show(names, npc_id)}: "{r["text"]}"')
    return ["Night thoughts:", *lines] if lines else []


def format_story(events: list[Event], names: dict[str, str], sidecar: dict | None = None) -> str:
    """The full transcript: days, events, night thoughts, then ground truth and stats."""
    sidecar = sidecar or {}
    reflections = sidecar.get("reflections", {})
    # A day with only night thoughts (no events) still deserves its header.
    days = {e.tick // MINUTES_PER_DAY + 1 for e in events}
    days |= {r["tick"] // MINUTES_PER_DAY + 1 for rs in reflections.values() for r in rs}
    out = []
    for day in sorted(days):
        out.append(f"=== Day {day} ===")
        for e in events:
            if e.tick // MINUTES_PER_DAY + 1 == day and (line := format_event(e, names)):
                out.append(line)
        thoughts = night_thoughts(reflections, day, names)
        out += ["", *thoughts] if thoughts else []
        out.append("")
    if sidecar.get("secrets"):
        out.append("Ground truth:")
        for key, value in sorted(sidecar["secrets"].items()):
            out.append(f"  {key}: {show(names, value) if isinstance(value, str) else value}")
    if "stats" in sidecar:
        out.append(f"Stats: {stats_line(sidecar['stats'])}")
    return "\n".join(out).rstrip()
