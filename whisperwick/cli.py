"""Command-line interface. Run `uv run whisperwick --help`."""

import json
import time
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from whisperwick import compare_command, llm_run, run_report, settings, story, trace_command
from whisperwick.belief_log import BeliefLog
from whisperwick.clock import Clock
from whisperwick.events import Event
from whisperwick.llm_client import OllamaClient
from whisperwick.llm_sim import run_llm
from whisperwick.player import PlayerSource
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


def llm_settings() -> tuple[str, str]:
    """The model server and name from .env. Stops with a hint if they are missing."""
    base_url, model = settings.llm_base_url(), settings.llm_model()
    if not base_url or not model:
        typer.echo("LLM_BASE_URL and LLM_MODEL are not set. Copy .env.example to .env.", err=True)
        raise typer.Exit(1)
    return base_url, model


def run_with_llm(
    sc,
    scenario: Path,
    db: str,
    seed: int | None,
    minutes: int,
    player: PlayerSource | None = None,
    player_name: str | None = None,
) -> None:
    """The LLM run: one progress line per game hour, then a sidecar next to the db.

    `play` shares this. With a player, the run may end early (quit) and is summed up too.
    """
    # Check settings first, so a bad setup leaves no empty db file behind.
    base_url, model = llm_settings()
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    world = build_world(sc, db, seed=seed)
    started = time.monotonic()
    start_tick = world.clock.tick

    def progress(w, stats):
        typer.echo(llm_run.progress_line(w.clock.label(), stats, time.monotonic() - started))

    client = OllamaClient(base_url, model)
    # Hourly progress would clutter a human's screen, so terminal play skips it.
    on_hour = None if isinstance(player, TerminalPlayer) else progress
    stats = {"player_rejected": []} if player else {}
    # Every thought is also saved as a JSON line next to the db.
    belief_log = BeliefLog(llm_run.beliefs_path(db))
    memories, stats = run_llm(
        world,
        client,
        minutes,
        stats=stats,
        evidence=sc.evidence,
        on_hour=on_hour,
        player=player,
        personalities=sc.personality,
        belief_log=belief_log,
    )
    # Read-only interview and final item places. Both go in the sidecar only.
    extra = run_report.after_run(world, memories, client, stats)
    typer.echo(f"\n{llm_run.stats_line(stats)}")
    if stats.get("stopped"):
        # Said loudly: a stopped run is not a normal result (#34).
        typer.echo(f"RUN STOPPED EARLY: {stats['stopped']}")
    typer.echo("Interview (who killed the mayor?):")
    names = {i: n.name for i, n in world.npcs.items()}
    typer.echo("\n".join(run_report.summary_lines(extra["interview"], names, belief_log)))
    if player:
        typer.echo(f"Player steps rejected: {len(stats['player_rejected'])}")
    typer.echo(f"Events: {db}")
    path = llm_run.sidecar_path(db)
    # Minutes actually played: a quit can end the run early.
    played = world.clock.tick - start_tick
    data = llm_run.sidecar_data(
        scenario, model, played, stats, sc.secrets, memories, player_name, belief_log.path
    )
    data.update(extra)
    llm_run.write_sidecar(path, data)
    typer.echo(f"Sidecar: {path}")


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
    subject: Annotated[str, typer.Argument(help="Person id, e.g. npc_hal.")],
    as_json: Annotated[bool, typer.Option("--json", help="Print the trace as JSON.")] = False,
) -> None:
    """Who believes SUBJECT did it, and via whom (from the belief log). No model is called."""
    try:
        typer.echo(trace_command.trace_run(db, subject, as_json))
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
