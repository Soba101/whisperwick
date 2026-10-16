"""Small command surface for replay checks, fixed turn lists and model screens."""

import json
import time
from pathlib import Path
from typing import Annotated

import typer

from whisperwick import llm_cli, settings
from whisperwick.screen_replay import check as replay_check
from whisperwick.screen_results import run_picked
from whisperwick.screen_turns import pick as pick_turns

app = typer.Typer(help="Screen model replies against parser and engine facts.")


def write(path, data):
    """Keep saved reports readable and stable for later comparisons."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def show(results):
    """Use the same measures and order for every compared run."""
    keys = ("turns", "calls", "parse_rate", "first_try_accepted", "rejected_share", "repeats",
            "accepted_after_retry", "fell_back_to_look", "requests_per_turn", "recalls",
            "latency_mean_s", "latency_p90_s", "prompt_ms_mean", "ms_per_output_token_mean",
            "prompt_tokens", "output_tokens",
            "thought_parse_rate", "citation_validity", "minutes")
    typer.echo("measure\t" + "\t".join(results))
    for key in keys:
        values = [data.get(key) for data in results.values()]
        typer.echo(key + "\t" + "\t".join(
            f"{v:.4f}" if isinstance(v, float) else str(v) for v in values))


@app.command("check")
def check_command(dbs: Annotated[list[Path], typer.Argument()]):
    """Replay without a model and report the first difference per run."""
    # Check all inputs so one bad run does not hide problems in the rest.
    failed = False
    for db in dbs:
        try:
            result = replay_check(db)
            text = "ok" if result["ok"] else result["difference"]
            typer.echo(f"{db}: {text}; unused recalls={result['unused_recalls']}")
            failed |= not result["ok"]
        except (OSError, ValueError) as exc:
            typer.echo(f"{db}: {exc}")
            failed = True
    if failed:
        raise typer.Exit(1)


@app.command("pick")
def pick_command(
    dbs: Annotated[list[Path], typer.Argument()],
    out: Annotated[Path, typer.Option()],
    acts: int = 300, thinks: int = 50, seed: int = 9,
):
    """Save a seeded uniform sample after checking every replay."""
    try:
        write(out, pick_turns(dbs, acts, thinks, seed))
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Wrote {out}")


@app.command("run")
def run_command(
    turns_file: Annotated[Path, typer.Argument()],
    out: Annotated[Path, typer.Option()],
    base_url: str | None = None, model: str | None = None,
):
    """Ask a candidate at the saved turns, on disposable copies."""
    base_url = base_url or settings.llm_base_url()
    model = model or settings.llm_model()
    if not base_url or not model:
        # Keep the usual missing-settings message when neither overrides nor .env suffice.
        llm_cli.llm_settings()
    # Include replay and scoring time in the reported wall time.
    started = time.monotonic()
    try:
        client = llm_cli.make_client(settings.llm_server(), base_url, model)
        result = run_picked(json.loads(turns_file.read_text()), client)
        # Save candidate settings so reports can be traced to their source.
        result.update(model=model, base_url=base_url)
        result["totals"]["minutes"] = (time.monotonic() - started) / 60
        write(out, result)
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    show({model: result["totals"]})
    typer.echo(f"Wrote {out}")


@app.command("table")
def table_command(files: Annotated[list[Path], typer.Argument()]):
    """Compare the totals of saved screens side by side."""
    show({str(path): json.loads(path.read_text())["totals"] for path in files})
