"""The "Decisive" stall measure. Read-only: it only looks at events already logged.

While the case is open the guard can act on his doubt (move, take, show, look...) or stand
still and talk. Not arresting is his right; this only shows how long he stood still.
"""

from pathlib import Path

from whisperwick.eval_loop import longest_gap_hours
from whisperwick.player import PLAYER_ID
from whisperwick.scenario import load_scenario

# Things a guard does about a case. Talk is left out on purpose: talking in place is the stall.
ACTS = ("move", "take", "show", "give", "drop", "look", "arrest", "release")

NO_STALL = {"guard_stall_hours": None, "guard_acts_open": None}


def authority_of(sidecar: dict) -> list[str]:
    """Who may arrest, from the scenario file (ids, never names). Empty if the file is gone."""
    path = sidecar.get("scenario")
    if path and Path(path).is_file():
        return list(load_scenario(path).authority)
    return []


def stall_measures(events, authority: list[str], start: int, end: int) -> dict:
    """Longest waking stretch an arrester did nothing countable while the case was open.

    The case opens at the run start and closes at the first villager arrest, or the run end.
    """
    if not authority:
        return dict(NO_STALL)
    npc = [e for e in events if e.actor != PLAYER_ID]
    arrests = [e.tick for e in npc if e.type == "arrest"]
    close = max(start, min(arrests, default=end))
    worst, acts = 0.0, 0
    for who in authority:
        # Only this arrester's own acts, and only while the case was open.
        mine = sorted(
            e.tick for e in npc if e.actor == who and e.type in ACTS and start <= e.tick <= close
        )
        acts += len(mine)
        worst = max(worst, longest_gap_hours([start, *mine, close]))
    return {"guard_stall_hours": worst, "guard_acts_open": acts}
