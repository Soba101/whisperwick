"""LLM run setup shared by the run, play and judge commands (kept out of cli.py)."""

import time
from pathlib import Path

import typer

from whisperwick import judge_kev, judge_run, llm_run, run_report, settings
from whisperwick.agent_log import AgentLog, sidecar_part
from whisperwick.belief_log import BeliefLog
from whisperwick.kev_client import MODEL, KevClient
from whisperwick.llm_client import LlamaServerClient, OllamaClient
from whisperwick.llm_sim import run_llm
from whisperwick.notebook import Notebooks
from whisperwick.player import PlayerSource
from whisperwick.player_terminal import TerminalPlayer
from whisperwick.player_web import WebPlayer
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
    on_event=None,  # optional live-display hooks, passed to run_llm
    on_turn=None,
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
        slots = settings.llm_slots()
        group_turns = settings.group_turns()
        stream_talk = settings.stream_talk(isinstance(player, WebPlayer))
        settings.recall_rank()  # Validate recall ranking before creating the db.
        temperature = settings.llm_temperature()
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
    client.temperature = temperature  # both clients read it on every call
    if server == "llama-server":
        model = f"{model} via llama-server"  # the sidecar says which server was used
    if temperature != 0.7:
        model = f"{model} at temperature {temperature}"  # so a run's sidecar shows the change
    # Hourly progress would clutter a human's screen, so terminal and web play skip it.
    on_hour = None if isinstance(player, TerminalPlayer | WebPlayer) else progress
    stats = {"player_rejected": []} if player else {}
    if isinstance(player, WebPlayer):
        if stream_talk and isinstance(client, LlamaServerClient):
            client.live_talk = player.on_live_talk
        player.stats = stats  # the page can tell a model error from a plain look (#76)
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
        slots=slots,
        group_turns=group_turns,
        agent_memory=agent_memory,
        notebooks=notebooks,
        agent_log=agent_log,
        on_event=on_event,
        on_turn=on_turn,
    )
    # Read-only interview and final item places. Both go in the sidecar only.
    if sc.crime_seed is None:
        extra = run_report.after_run(world, memories, client, stats)
    else:
        extra = run_report.after_run(world, memories, client, stats, sc.secrets["victim"])
    typer.echo(f"\n{llm_run.stats_line(stats)}")
    if stats.get("stopped"):
        # Said loudly: a stopped run is not a normal result (#34).
        typer.echo(f"RUN STOPPED EARLY: {stats['stopped']}")
    label = "the mayor" if sc.crime_seed is None else world.npcs[sc.secrets["victim"]].name
    typer.echo(f"Interview (who killed {label}?):")
    names = {i: n.name for i, n in world.npcs.items()}
    typer.echo("\n".join(run_report.summary_lines(extra["interview"], names, belief_log)))
    if player:
        typer.echo(f"Player steps rejected: {len(stats['player_rejected'])}")
    typer.echo(f"Events: {db}")
    path = llm_run.sidecar_path(db)
    # Minutes actually played: a quit can end the run early.
    played = world.clock.tick - start_tick
    data = llm_run.sidecar_data(
        scenario, model, played, stats, sc.secrets, memories, player_name, belief_log.path,
        client,
    )
    data["authority"] = sc.authority
    if sc.crime_seed is not None:
        data["crime_seed"] = sc.crime_seed
    if sc.role_id:
        data.update(role=sc.role_id, private_fact=sc.private_fact, player_title=sc.player_title)
    data.update(extra)
    data["wishes"] = world.wishes
    data["group_turns"] = group_turns
    # The seed lets `eval` group runs that differ only in the player script.
    data["seed"] = sc.seed if seed is None else seed
    data.update(sidecar_part(agent_memory, agent_log, notebooks))
    llm_run.write_sidecar(path, data)
    if isinstance(player, WebPlayer):
        # Serialize with an accusation that may arrive just as the run ends.
        with player.cv:
            player.ending.sidecar = path
            player.ending.save()
    typer.echo(f"Sidecar: {path}")


def judge_client():
    """The judge's client, model name and judge function.

    "same" asks the run's chat model at temperature 0, so the same run gets the same
    grades. "kev" asks the Kev judge server, which needs no chat settings.
    """
    try:
        which = settings.judge_server()
        if which == "kev":
            return KevClient(settings.kev_url(), settings.kev_api_key()), MODEL, judge_kev.judge
        server = settings.llm_server()
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    base_url, model = llm_settings()
    client = make_client(server, base_url, model, temperature=0.0)
    return client, model, judge_run.judge
