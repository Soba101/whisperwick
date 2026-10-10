"""Replay a run from its events: who is where, who is held. Code only, no model.

The page does the same replay in JavaScript so the slider is instant. This Python
version is the reference: tests check it against hand-made event lists.
World facts only. Nothing here reads a secret or a belief.
"""

import math

from whisperwick.events import Event
from whisperwick.scenario import Scenario


def layout(scenario: Scenario) -> dict[str, tuple[float, float]]:
    """A fixed spot (x, y as percent of the map) for each place, evenly on a circle.

    Same scenario in, same spots out. The first place sits at the top.
    """
    places = scenario.locations
    spots = {}
    for i, loc in enumerate(places):
        angle = 2 * math.pi * i / max(len(places), 1) - math.pi / 2
        # Narrower across than down: a box is wider than tall, and at 34 across the
        # left and right boxes were cut off at the map's edge.
        spots[loc.id] = (round(50 + 26 * math.cos(angle), 1), round(50 + 34 * math.sin(angle), 1))
    return spots


def start_state(scenario: Scenario) -> dict:
    """Where everyone is before the first event, and nobody is held."""
    return {"positions": {n.id: n.location for n in scenario.npcs}, "held": {}}


def apply_event(state: dict, e: Event) -> None:
    """Change the state by one event. Only moves and custody change who is where."""
    if e.type == "move":
        state["positions"][e.actor] = e.data["to"]
    elif e.type == "arrest":
        state["held"][e.data["target"]] = e.actor  # target -> who holds them
    elif e.type == "release":
        state["held"].pop(e.data["target"], None)


def state_at(scenario: Scenario, events: list[Event], tick: int) -> dict:
    """The state after every event with tick <= the given tick."""
    state = start_state(scenario)
    for e in events:
        if e.tick <= tick:
            apply_event(state, e)
    return state
