"""Local invite management. Only invite prints the newly minted secret."""

import json
from typing import Annotated

import typer

from whisperwick import feedback
from whisperwick.invite_actions import invite_link
from whisperwick.invite_files import locked, rows
from whisperwick.invite_players import Players
from whisperwick.invite_requests import Requests


def requests() -> None:
    """List waiting requests."""
    path = feedback.DEFAULT_PATH.with_name("requests.jsonl")
    for entry in rows(path):
        typer.echo(json.dumps(entry))


def invite(
    name: Annotated[str, typer.Argument(help="Player name.")],
    approve: Annotated[bool, typer.Option(help="Require a waiting request.")] = False,
    host: Annotated[str | None, typer.Option(help="Public HTTPS host for the link.")] = None,
) -> None:
    """Create a personal key and print its link once."""
    folder = feedback.DEFAULT_PATH.parent
    try:
        link = invite_link(Players(folder), name, approve, host)
    except (ValueError, OSError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(link)


def decline(name: Annotated[str, typer.Argument(help="Waiting player name.")]) -> None:
    """Remove a waiting request without granting access."""
    try:
        Requests(feedback.DEFAULT_PATH.parent).decline(name)
    except (ValueError, OSError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo("Request declined.")


def players() -> None:
    """List players and their usage, without exposing key hashes."""
    store = Players(feedback.DEFAULT_PATH.parent)
    with locked(store.folder):
        # Only live links, as on the admin page.
        for player in (p for p in store.read() if not p["revoked"]):
            typer.echo(json.dumps({k: v for k, v in player.items() if k != "key_hash"}))


def revoke(name: Annotated[str, typer.Argument(help="Player name.")]) -> None:
    """Refuse this player's key on their next request."""
    try:
        Players(feedback.DEFAULT_PATH.parent).revoke(name)
    except (ValueError, OSError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo("Player revoked.")
