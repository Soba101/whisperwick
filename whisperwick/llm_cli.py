"""LLM run setup shared by the run, play and judge commands (kept out of cli.py)."""

import time
from pathlib import Path

import typer

from whisperwick import llm_run, run_report, settings
from whisperwick.agent_log import AgentLog, sidecar_part
from whisperwick.belief_log import BeliefLog
from whisperwick.llm_client import LlamaServerClient, OllamaClient
from whisperwick.llm_sim import run_llm
from whisperwick.notebook import Notebooks
from whisperwick.player import PlayerSource
from whisperwick.player_terminal import TerminalPlayer
from whisperwick.scenario import build_world


def llm_settings() -> tuple[str, str]:
    """The model server and name from .env. Stops with a hint if they are missing."""
    base_url, model = settings.llm_base_url(), settings.llm_model()
    if not base_url or not model:
        typer.echo("LLM_BASE_URL and LLM_MODEL are not set. Copy .env.example to .env.", err=True)
        raise typer.Exit(1)
    return base_url, model


def make_client(server: str, base_url: str, model: str, temperature: float = 0.7):
    """Pick the client class for LLM_SERVER. The judge asks for temperature 0."""
    if server == "llama-server":
        return LlamaServerClient(base_url, model, temperature=temperature)
    return OllamaClient(base_url, model, temperature=temperature)


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
    try:
        parallel = settings.parallel()
        server = settings.llm_server()
        agent_memory = settings.agent_memory()
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    world = build_world(sc, db, seed=seed)
    started = time.monotonic()
    start_tick = world.clock.tick

    def progress(w, stats):
        typer.echo(llm_run.progress_line(w.clock.label(), stats, time.monotonic() - started))

    client = make_client(server, base_url, model)
    if server == "llama-server":
        model = f"{model} via llama-server"  # the sidecar says which server was used
    # Hourly progress would clutter a human's screen, so terminal play skips it.
    on_hour = None if isinstance(player, TerminalPlayer) else progress
    stats = {"player_rejected": []} if player else {}
    # Every thought is also saved as a JSON line next to the db.
    belief_log = BeliefLog(llm_run.beliefs_path(db))
    # Recall searches are saved as JSON lines too. Notebooks are read back at the end.
    agent_log = AgentLog(llm_run.agent_log_path(db))
    notebooks = Notebooks()
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
        parallel=parallel,
        agent_memory=agent_memory,
        notebooks=notebooks,
        agent_log=agent_log,
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
    # The seed lets `eval` group runs that differ only in the player script.
    data["seed"] = sc.seed if seed is None else seed
    data.update(sidecar_part(agent_memory, agent_log, notebooks))
    llm_run.write_sidecar(path, data)
    typer.echo(f"Sidecar: {path}")


def judge_client():
    """The judge's model and client. Temperature 0, so the same run gets the same grades."""
    base_url, model = llm_settings()
    try:
        server = settings.llm_server()
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    return make_client(server, base_url, model, temperature=0.0), model
