"""Command-line interface. Run `uv run whisperwick --help`."""

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from whisperwick import (
    compare_command,
    eval_command,
    event_trace_command,
    judge_command,
    llm_run,
    outcome_command,
    replay_command,
    story,
)
from whisperwick.clock import Clock
from whisperwick.events import Event
from whisperwick.llm_cli import judge_client, run_with_llm
from whisperwick.player_script import load_script
from whisperwick.player_terminal import TerminalPlayer
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


class Agent(StrEnum):
    stub = "stub"  # scripted, no model needed
    llm = "llm"  # a real model server, set up in .env


@app.command()
def run(
    # Annotated options are Typer's recommended style (and keep the linter happy).
    scenario: Annotated[Path, typer.Option(help="Scenario YAML file.")] = DEFAULT_SCENARIO,
    hours: Annotated[int, typer.Option(help="Game hours to simulate.")] = 24,
    days: Annotated[int | None, typer.Option(help="Game days. Overrides --hours.")] = None,
    agent: Annotated[Agent, typer.Option(help="stub = scripted, llm = real model.")] = Agent.stub,
    seed: Annotated[int | None, typer.Option(help="Override the scenario's seed.")] = None,
    db: Annotated[
        str | None, typer.Option(help="SQLite file for the event log, e.g. data/run.db")
    ] = None,
) -> None:
    """Run a scenario. The stub agent prints every event; the llm agent saves a story."""
    sc = load_scenario(scenario)
    minutes = days * 24 * 60 if days else hours * 60
    if agent == Agent.llm:
        run_with_llm(sc, scenario, db or llm_run.default_db_path(sc.name), seed, minutes)
        return
    world = build_world(sc, db or ":memory:", seed=seed)
    run_sim(world, minutes=minutes)

    for e in world.log.all():
        seen = ", ".join(e.witnesses) or "nobody"
        typer.echo(f"{Clock(e.tick).label()}  {describe(e)}  (seen by {seen})")
    typer.echo(f"\n{len(world.log.all())} events.")


@app.command()
def play(
    script: Annotated[
        Path | None, typer.Option(help="Player script YAML. Without it you play in the terminal.")
    ] = None,
    scenario: Annotated[Path, typer.Option(help="Scenario YAML file.")] = DEFAULT_SCENARIO,
    days: Annotated[int, typer.Option(help="Game days to play.")] = 1,
    seed: Annotated[int | None, typer.Option(help="Override the scenario's seed.")] = None,
    db: Annotated[str | None, typer.Option(help="SQLite file for the event log.")] = None,
) -> None:
    """Play Wren in the village (terminal), or run a player script. Needs a model server."""
    sc = load_scenario(scenario)
    try:
        player = load_script(script) if script else TerminalPlayer()
    except (ValueError, OSError) as e:
        # A broken script is a data bug: say so plainly instead of a traceback.
        typer.echo(f"Bad player script: {e}", err=True)
        raise typer.Exit(1) from e
    name = getattr(player, "name", "terminal")
    run_with_llm(
        sc, scenario, db or llm_run.default_db_path(sc.name), seed, days * 24 * 60, player, name
    )


@app.command("story")
def story_command(
    db: Annotated[Path, typer.Argument(help="Event log from an llm run.")],
    sidecar: Annotated[
        Path | None, typer.Option("--json", help="Sidecar JSON. Default: next to the db.")
    ] = None,
) -> None:
    """Print a readable transcript of a saved run. No model is called."""
    if not db.is_file():
        typer.echo(f"No such file: {db}", err=True)
        raise typer.Exit(1)
    sidecar = sidecar or llm_run.sidecar_path(db)
    data = json.loads(sidecar.read_text()) if sidecar.is_file() else None
    # Names come from the scenario the run used. If it moved, fall back to ids.
    sc_path = Path(data["scenario"]) if data else None
    sc = load_scenario(sc_path) if sc_path and sc_path.is_file() else None
    typer.echo(story.format_story(story.read_events(db), story.names_from(sc), data))


@app.command("compare")
def compare_command_(
    dbs: Annotated[list[Path], typer.Argument(help="Two or more event logs from llm runs.")],
) -> None:
    """Compare runs side by side: suspects, items, key events. No model is called."""
    try:
        typer.echo(compare_command.compare_runs(dbs))
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e


@app.command("trace")
def trace_command_(
    db: Annotated[Path, typer.Argument(help="Event log from an llm run.")],
    subject: Annotated[str | None, typer.Argument(help="Person id, e.g. npc_hal.")] = None,
    event: Annotated[int | None, typer.Option("--event", help="Explain this event id.")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the trace as JSON.")] = False,
) -> None:
    """Who believes SUBJECT did it, or (--event N) why event N happened. No model is called."""
    try:
        typer.echo(event_trace_command.trace_any(db, subject, event, as_json))
    except (FileNotFoundError, ValueError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e


@app.command("outcome")
def outcome_command_(
    db: Annotated[Path, typer.Argument(help="Event log from an llm run.")],
    scenario: Annotated[
        Path | None, typer.Option(help="Scenario YAML. Only given to also print its secret.")
    ] = None,
) -> None:
    """Arrests, releases and who is held at the end. World events only. No model is called."""
    try:
        typer.echo(outcome_command.outcome_run(db, scenario))
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e


@app.command("eval")
def eval_command_(
    dbs: Annotated[list[Path], typer.Argument(help="One or more event logs from llm runs.")],
) -> None:
    """Code-only measures per run, then a summary across runs. No model is called."""
    try:
        typer.echo(eval_command.eval_runs(dbs))
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e


@app.command("replay")
def replay_command_(
    db: Annotated[Path, typer.Argument(help="Event log from a finished run.")],
    out: Annotated[Path | None, typer.Option(help="Where to write the HTML page.")] = None,
    scenario: Annotated[
        Path | None, typer.Option(help="Scenario YAML for names and the map.")
    ] = None,
) -> None:
    """Write one self-contained HTML page that replays the run. World facts only."""
    try:
        typer.echo(f"Wrote {replay_command.replay_run(db, out, scenario)}")
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e


@app.command("judge")
def judge_command_(
    db: Annotated[Path, typer.Argument(help="Event log from a finished llm run.")],
    limit: Annotated[int, typer.Option(help="Items per question type.")] = 40,
) -> None:
    """Ask the model to grade a finished run. Run it only when no village run is going."""
    if not db.is_file():
        typer.echo(f"No such file: {db}", err=True)
        raise typer.Exit(1)
    client, model = judge_client()
    typer.echo(judge_command.judge_run_command(db, client, model, limit))
