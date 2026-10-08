"""Command-line interface. Run `uv run whisperwick --help`."""

from pathlib import Path
from typing import Annotated

import typer

from whisperwick.clock import Clock
from whisperwick.scenario import build_world, load_scenario
from whisperwick.sim import run as run_sim

app = typer.Typer(help="Whisperwick: a village of agents with their own beliefs.")

DEFAULT_SCENARIO = Path("scenarios/murder_of_the_mayor.yaml")


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
    world = build_world(sc, db)
    run_sim(world, minutes=hours * 60, seed=sc.seed if seed is None else seed)

    # Week 1 only has "move" events. Generalise this print once more types exist.
    for e in world.log.all():
        when = Clock(e.tick).label()
        seen = ", ".join(e.witnesses) or "nobody"
        move = f"{e.data['from']} -> {e.data['to']}"
        typer.echo(f"{when}  {e.actor} {e.type} {move}  (seen by {seen})")
    typer.echo(f"\n{len(world.log.all())} events.")
