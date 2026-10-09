"""Scripted player: a YAML file of timed steps.

A broken script is our data bug, so loading raises ValueError with a clear message.
Ids are not checked here: the engine rejects bad ids at run time, like for any actor.
"""

import re
from collections.abc import Callable
from pathlib import Path

import yaml

from whisperwick.actions import ActionResult, Intent
from whisperwick.clock import Clock
from whisperwick.player import PLAYER_ID, PlayerSource

STEP_KEYS = {"at", "action", "target", "item", "message", "claim"}
AT_FORMAT = re.compile(r"^(\d+) (\d{1,2}):(\d{2})$")  # "1 09:00" = day 1, 09:00


def parse_at(text) -> int:
    """'1 09:00' -> tick. Uses the clock's own convention: day 1 starts at tick 0."""
    m = AT_FORMAT.match(str(text).strip())
    if not m:
        raise ValueError(f'bad time {text!r}: use "<day> HH:MM", e.g. "1 09:00"')
    day, hour, minute = (int(g) for g in m.groups())
    if day < 1 or hour > 23 or minute > 59:
        raise ValueError(f"bad time {text!r}: day starts at 1, hour 0-23, minute 0-59")
    return Clock.at(day, hour, minute).tick


def parse_steps(data) -> tuple[str | None, dict[int, list[Intent]]]:
    """Check a loaded YAML document. Returns (name, tick -> intents in file order)."""
    if not isinstance(data, dict) or "steps" not in data:
        raise ValueError("script needs a top-level 'steps:' list")
    if set(data) - {"name", "steps"}:
        raise ValueError(f"unknown top-level keys: {sorted(set(data) - {'name', 'steps'})}")
    steps = data["steps"] or []
    if not isinstance(steps, list):
        raise ValueError("'steps' must be a list")
    script: dict[int, list[Intent]] = {}
    for i, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise ValueError(f"step {i}: must be a mapping")
        if set(step) - STEP_KEYS:
            raise ValueError(f"step {i}: unknown keys {sorted(set(step) - STEP_KEYS)}")
        if "at" not in step or "action" not in step:
            raise ValueError(f"step {i}: needs 'at' and 'action'")
        try:
            tick = parse_at(step["at"])
        except ValueError as e:
            raise ValueError(f"step {i}: {e}") from e
        fields = {k: v for k, v in step.items() if k != "at"}
        script.setdefault(tick, []).append(Intent(actor=PLAYER_ID, **fields))
    return data.get("name"), script


def load_script(path: str | Path) -> "ScriptedPlayer":
    path = Path(path)
    name, script = parse_steps(yaml.safe_load(path.read_text()))
    return ScriptedPlayer(script, name or path.stem)


class ScriptedPlayer(PlayerSource):
    def __init__(
        self,
        script: dict[int, list[Intent]],
        name: str = "script",
        output_fn: Callable[[str], None] = print,
    ):
        self.script = script
        self.name = name
        self.output_fn = output_fn
        self.checked = False  # past steps are reported once, on the first turn

    def turn(self, world) -> list[Intent]:
        if not self.checked:
            # A step timed before the run starts would never run. Say so, once,
            # instead of silently dropping it.
            self.checked = True
            late = sorted(t for t in self.script if t < world.clock.tick)
            for t in late:
                self.output_fn(f"Script step at {Clock(t).label()} is before the start: skipped")
        return self.script.get(world.clock.tick, [])

    def report(self, intent: Intent, result: ActionResult) -> None:
        # A rejected step is a note, not a crash.
        if not result.ok:
            self.output_fn(f"Script step rejected ({intent.action}): {result.reason}")
