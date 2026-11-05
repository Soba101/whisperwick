"""Scripted run output and sidecar, with no model server involved."""

import typer

from whisperwick import llm_run, run_setup
from whisperwick.clock import Clock
from whisperwick.events import Event
from whisperwick.memory import Memories
from whisperwick.scenario import build_world
from whisperwick.sim import run as run_sim


def describe(e: Event) -> str:
    """One readable line per event type. Add a branch when adding an action."""
    if e.type == "move":
        return f"{e.actor} walks {e.data['from']} -> {e.data['to']}"
    if e.type == "talk":
        return f'{e.actor} to {e.data["to"]}: "{e.data["message"]}"'
    return f"{e.actor} {e.type} {e.data}"


def run(sc, scenario, db: str | None, seed: int | None, minutes: int) -> None:
    """Keep the same seeded loop. Provenance stays outside world state."""
    setup = run_setup.collect_setup()
    world = build_world(sc, db or ":memory:", seed=seed)
    run_sim(world, minutes=minutes)

    for e in world.log.all():
        seen = ", ".join(e.witnesses) or "nobody"
        typer.echo(f"{Clock(e.tick).label()}  {describe(e)}  (seen by {seen})")
    typer.echo(f"\n{len(world.log.all())} events.")
    # An in-memory run has no saved database to accompany with a sidecar.
    if db and db != ":memory:":
        data = llm_run.sidecar_data(
            scenario, "stub", minutes, {}, sc.secrets, Memories(), setup=setup,
        )
        data["seed"] = sc.seed if seed is None else seed
        llm_run.write_sidecar(llm_run.sidecar_path(db), data)
