"""Command-line interface. Run `uv run whisperwick --help`."""

from pathlib import Path
from typing import Annotated

import typer

from whisperwick.clock import Clock
from whisperwick.events import Event
from whisperwick.scenario import build_world, load_scenario
from whisperwick.sim import run as run_sim

app = typer.Typer(help="Whisperwick: a village of agents with their own beliefs.")

DEFAULT_SCENARIO = Path("scenarios/murder_of_the_mayor.yaml")


def describe(e: Event) -> str:
    """One readable line per event type. Add a branch when adding an action."""
    if e.type == "move":
        return f"{e.actor} walks {e.data['from']} -> {e.data['to']}"
    if e.type == "talk":
        return f'{e.actor} to {e.data["to"]}: "{e.data["message"]}"'
    return f"{e.actor} {e.type} {e.data}"


@app.callback()
def main() -> None:
    """Keeps `run` as a named sub-command, so more commands can be added later."""


@app.command()
def run(
    # Annotated options are Typer's recommended style (and keep the linter happy).
    scenario: Annotated[Path, typer.Option(help="Scenario YAML file.")] = DEFAULT_SCENARIO,
    hours: Annotated[int, typer.Option(help="Game hours to simulate.")] = 24,
    seed: Annotated[int | None, typer.Option(help="Override the scenario's seed.")] = None,
    db: Annotated[
        str, typer.Option(help="SQLite file for the event log, e.g. data/run.db")
    ] = ":memory:",
) -> None:
    """Run a scenario and print every event."""
    sc = load_scenario(scenario)
    world = build_world(sc, db, seed=seed)
    run_sim(world, minutes=hours * 60)

    for e in world.log.all():
        seen = ", ".join(e.witnesses) or "nobody"
        typer.echo(f"{Clock(e.tick).label()}  {describe(e)}  (seen by {seen})")
    typer.echo(f"\n{len(world.log.all())} events.")
