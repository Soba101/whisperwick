"""Beliefs for a finished run, rebuilt from its files with no model.

The event log plus the scenario is all a belief needs (see beliefs.py), so any
saved run, old or new, can be replayed. Old week 3 runs have no claims in their
logs: they just give the starting beliefs and the clue sightings. That is fine.
"""

import json
from pathlib import Path

from whisperwick import story
from whisperwick.beliefs import BeliefState, replay
from whisperwick.events import EventLog
from whisperwick.llm_run import sidecar_path
from whisperwick.player import PLAYER_ID
from whisperwick.scenario import Scenario, load_scenario

# Used when a run has no sidecar, or its scenario file has moved.
DEFAULT_SCENARIO = Path(__file__).parent.parent / "scenarios" / "murder_of_the_mayor.yaml"


def scenario_for_run(db: str | Path) -> Scenario:
    """The scenario named in the sidecar, else the default one."""
    side = sidecar_path(db)
    try:
        path = json.loads(side.read_text()).get("scenario") if side.is_file() else None
    except (OSError, ValueError):
        path = None  # a broken sidecar just means: use the default
    return load_scenario(path if path and Path(path).is_file() else DEFAULT_SCENARIO)


def beliefs_for_run(db: str | Path) -> BeliefState:
    """Replay the run's events (read-only) into beliefs and trust."""
    return replay(EventLog.read(str(db)), scenario_for_run(db))


def belief_answer(state: BeliefState, npc_id: str) -> dict:
    """What the code says this villager believes: top suspect, never themselves."""
    top = state.top(npc_id, exclude={npc_id})
    return {
        "belief_suspect": top[0] if top else None,
        "belief_confidence": top[1] if top else None,
    }


def pct(x: float) -> str:
    return f"{x:.0%}"


def belief_text(suspect: str | None, confidence: float | None, names: dict[str, str]) -> str:
    """e.g. 'Victor 65%', or '-' when the villager suspects nobody."""
    return f"{story.show(names, suspect)} {pct(confidence)}" if suspect else "-"


def belief_cell(state: BeliefState | None, npc_id: str, names: dict[str, str]) -> str:
    """One cell of the compare table. '-' when the run could not be replayed."""
    if state is None:
        return "-"
    a = belief_answer(state, npc_id)
    return belief_text(a["belief_suspect"], a["belief_confidence"], names)


def villagers(state: BeliefState) -> list[str]:
    """Everyone who holds a belief or has a changed trust, except the player."""
    return sorted((set(state.conf) | set(state.trust.pairs)) - {PLAYER_ID})


def trust_in_player_line(state: BeliefState | None, names: dict[str, str]) -> str:
    """e.g. 'Alice 30%, Bob 15%': each villager's final trust in the player."""
    if state is None or not villagers(state):
        return "-"
    return ", ".join(
        f"{story.show(names, v)} {pct(state.trust.get(v, PLAYER_ID))}" for v in villagers(state)
    )
