"""`play --web`: the game loop in a background thread, the page served from this one."""

import threading
from pathlib import Path

import typer

from whisperwick.llm_cli import llm_settings, run_with_llm
from whisperwick.player_web import WebPlayer
from whisperwick.scenario import Scenario
from whisperwick.web_server import make_server


def start(sc: Scenario, scenario: Path, db: str, seed: int | None, minutes: int, port: int):
    """Start the server and the game thread. Returns (server, player, game thread)."""
    player = WebPlayer(sc)
    server = make_server(player, port)

    def game() -> None:
        error = None
        try:
            run_with_llm(sc, scenario, db, seed, minutes, player, "web")
        except Exception as e:  # shown on the page, so a crash is not a silent stall
            error = f"the game stopped: {e}"
        # The last minute has no quit, so the end is marked here (after the run's summary).
        player.finish(error)

    thread = threading.Thread(target=game, daemon=True)
    thread.start()
    return server, player, thread


def serve(sc: Scenario, scenario: Path, db: str, seed: int | None, minutes: int, port: int) -> None:
    """Play until Ctrl-C. The page stays up after the game so the outcome can be read."""
    llm_settings()  # stops early, with a hint, if the model server is not set up
    try:
        server, player, _ = start(sc, scenario, db, seed, minutes, port)
    except OSError as e:
        # Another program has the port (Docker Desktop holds 8000 on this Mac).
        hint = f"whisperwick play --web --port {port + 1}"
        typer.echo(f"Port {port} is in use ({e.strerror}). Try: {hint}")
        raise typer.Exit(1) from e
    typer.echo(f"Play Wren at http://127.0.0.1:{server.server_address[1]}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        player.stop()
        server.server_close()
