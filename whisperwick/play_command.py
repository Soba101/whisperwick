"""Player command setup, kept separate from the report commands."""

from pathlib import Path
from typing import Annotated

import typer

from whisperwick import llm_run, web_play
from whisperwick.crime.selection import crime_number, select
from whisperwick.llm_cli import run_with_llm
from whisperwick.player_script import load_script
from whisperwick.player_terminal import TerminalPlayer
from whisperwick.roles import apply_role

DEFAULT_SCENARIO = Path("scenarios/murder_of_the_mayor.yaml")


def play(
    role: Annotated[str | None, typer.Option(help="cousin, peddler or partner.")] = None,
    script: Annotated[
        Path | None, typer.Option(help="Player script YAML. Without it you play in the terminal.")
    ] = None,
    scenario: Annotated[Path, typer.Option(help="Scenario YAML file.")] = DEFAULT_SCENARIO,
    crime: Annotated[str | None, typer.Option(help="Generate a crime: random or SEED.")] = None,
    days: Annotated[int, typer.Option(help="Game days to play.")] = 1,
    seed: Annotated[int | None, typer.Option(help="Override the scenario's seed.")] = None,
    db: Annotated[str | None, typer.Option(help="SQLite file for the event log.")] = None,
    web: Annotated[bool, typer.Option(help="Play in a local web page instead.")] = False,
    port: Annotated[int, typer.Option(help="Port for --web (127.0.0.1 only).")] = 8000,
    key: Annotated[
        str | None,
        typer.Option(
            help="--web: key every visitor needs (?key=KEY once).", envvar="WHISPERWICK_WEB_KEY"
        ),
    ] = None,
    allow_host: Annotated[
        list[str] | None, typer.Option(help="--web: extra Host name to accept (needs --key).")
    ] = None,
    max_games: Annotated[int, typer.Option(help="--web: games running at once.")] = 3,
) -> None:
    """Play Wren in the village (terminal or --web), or run a player script. Needs a model."""
    try:
        if web and crime is not None and crime != "random":
            crime_number(crime)
        # Web visitors draw their own crime only when they press Start.
        sc = select(scenario, None if web else crime)
    except ValueError as e:
        raise typer.BadParameter(str(e), param_hint="--crime") from e
    if sc.crime_seed is not None:
        typer.echo(f"Crime #{sc.crime_seed}")
    try:
        if role:
            apply_role(sc, role, seed)  # Validate before opening a server or model connection.
    except ValueError as e:
        raise typer.BadParameter(str(e), param_hint="--role") from e
    if web:
        db_path = db or llm_run.default_db_path(sc.name)
        return web_play.serve(
            sc, scenario, db_path, seed, days * 24 * 60, port, key, tuple(allow_host or ()),
            max_games, role=role, crime=crime,
        )
    sc = apply_role(sc, role, seed)
    if sc.player_title:
        typer.echo(f"You are {sc.player_title}.")
    if sc.private_fact:
        victim = next(n.name for n in sc.npcs if n.id == sc.secrets["victim"])
        typer.echo(f"Find out who killed {victim} before nightfall, or don't: it's your day.")
        typer.echo(f"What you know: {sc.private_fact}")
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

