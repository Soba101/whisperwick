"""`play --web`: one game loop per visitor in a background thread, the page served from here."""

import itertools
import threading
import time
from collections.abc import Callable
from pathlib import Path

import typer

from whisperwick.crime import generate
from whisperwick.crime.selection import crime_number
from whisperwick.llm_cli import llm_settings, run_with_llm
from whisperwick.player_web import WebPlayer
from whisperwick.roles import apply_role
from whisperwick.scenario import Scenario
from whisperwick.web_games import IDLE_SECONDS, MAX_GAMES, GameManager
from whisperwick.web_server import make_server


def launcher(
    sc: Scenario, scenario: Path, db_for: Callable[[int], str], seed: int | None, minutes: int
) -> Callable[..., tuple[WebPlayer, threading.Thread]]:
    """A function that starts one more game: its own player, its own db, its own thread."""
    numbers = itertools.count(1)  # db_for(n) gives each game a file, so runs never mix

    def launch(
        role: str | None = None, crime: str | None = None
    ) -> tuple[WebPlayer, threading.Thread]:
        base = sc if crime is None else generate(crime_number(crime))
        chosen = apply_role(base, role, seed)
        if chosen.crime_seed is not None:
            typer.echo(f"Crime #{chosen.crime_seed}")
        player, db = WebPlayer(chosen), db_for(next(numbers))

        def game() -> None:
            error = None
            try:
                # The hooks make lines and the "who is thinking" label appear at once.
                run_with_llm(chosen, scenario, db, seed, minutes, player, "web",
                             on_event=player.on_event, on_turn=player.on_turn)  # fmt: skip
            except Exception as e:  # shown on the page, so a crash is not a silent stall
                error = f"the game stopped: {e}"
            # The last minute has no quit, so the end is marked here (after the run's summary).
            player.finish(error)

        thread = threading.Thread(target=game, daemon=True)
        thread.start()
        return player, thread

    return launch


def start(
    sc: Scenario,
    scenario: Path,
    db_for: Callable[[int], str],
    seed: int | None,
    minutes: int,
    port: int,
    key: str | None = None,
    allow_hosts: tuple[str, ...] = (),
    max_games: int = MAX_GAMES,
    idle_seconds: float = IDLE_SECONDS,
    choose_roles: bool = False,
    role: str | None = None,
    crime: str | None = None,
):
    """Start the server. Games start when visitors arrive. Returns (server, game manager)."""
    manager = GameManager(
        launcher(sc, scenario, db_for, seed, minutes),
        max_games,
        idle_seconds,
        choose_roles=choose_roles,
        default_role=role,
        choose_crimes=crime is not None,
        default_crime=crime or "random",
    )
    return make_server(manager, port, key, allow_hosts), manager


def serve(
    sc: Scenario,
    scenario: Path,
    db: str,
    seed: int | None,
    minutes: int,
    port: int,
    key: str | None = None,
    allow_hosts: tuple[str, ...] = (),
    max_games: int = MAX_GAMES,
    role: str | None = None,
    crime: str | None = None,
) -> None:
    """Serve until Ctrl-C. A finished game's page stays up so the outcome can be read."""
    if allow_hosts and not key:
        # A public name without a key would let anyone start games on this computer.
        typer.echo("--allow-host needs --key (or WHISPERWICK_WEB_KEY).", err=True)
        raise typer.Exit(2)
    llm_settings()  # stops early, with a hint, if the model server is not set up
    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder = Path(db).parent

    def db_for(n: int) -> str:
        return str(folder / f"web-{stamp}-{n}.db")

    try:
        server, manager = start(
            sc,
            scenario,
            db_for,
            seed,
            minutes,
            port,
            key,
            allow_hosts,
            max_games,
            choose_roles=True,
            role=role,
            crime=crime or "random",
        )  # fmt: skip
    except OSError as e:
        # Another program has the port (Docker Desktop holds 8000 on this Mac).
        hint = f"whisperwick play --web --port {port + 1}"
        typer.echo(f"Port {port} is in use ({e.strerror}). Try: {hint}")
        raise typer.Exit(1) from e
    link = f"http://127.0.0.1:{server.server_address[1]}/" + (f"?key={key}" if key else "")
    typer.echo(f"Play Wren at {link}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        manager.close_all()
        server.server_close()
