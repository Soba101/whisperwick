"""Private player feedback. This module never submits an engine action."""

import hashlib
import json
import threading
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

TAGS = ("confusing", "too slow", "villagers ignored me", "bug", "loved it")
DEFAULT_PATH = Path("data/feedback.jsonl")
# One lock covers the limit check and complete line append across request threads.
_LOCK = threading.Lock()


def validate(body: dict) -> dict:
    """Accept only bounded, plain data. A bool is not a numeric rating."""
    if set(body) - {"page", "rating", "tags", "text"}:
        raise ValueError("unknown feedback field")
    page, rating = body.get("page"), body.get("rating")
    tags, text = body.get("tags", []), body.get("text", "")
    if page not in ("2d", "3d"):
        raise ValueError("page must be 2d or 3d")
    if rating is not None and rating != "" and (type(rating) is not int or not 1 <= rating <= 5):
        raise ValueError("rating must be 1-5 or empty")
    if not isinstance(tags, list) or len(tags) > len(TAGS):
        raise ValueError("invalid tags")
    if any(not isinstance(t, str) or t not in TAGS for t in tags):
        raise ValueError("invalid tags")
    if len(set(tags)) != len(tags):
        raise ValueError("duplicate tags")
    if not isinstance(text, str) or len(text) > 2000:
        raise ValueError("text must be at most 2000 characters")
    return {"page": page, "rating": None if rating == "" else rating, "tags": tags, "text": text}


def save(game, body: dict) -> tuple[int, dict]:
    try:
        fields = validate(body)
    except ValueError as e:
        return 400, {"error": str(e)}
    player = game.player
    # Read the cached player view, never the world database or its event log.
    with player.cv:
        context = {"crime": player.sc.crime_seed, "role": player.sc.role_id,
                   "clock": player.view.get("clock", "")}
    entry = {"time": datetime.now(UTC).isoformat(),
             "player": game.name,
             "game_id": hashlib.sha256(game.token.encode()).hexdigest(), **context, **fields}
    path = getattr(player, "feedback_path", DEFAULT_PATH)
    with _LOCK:
        if game.feedback_count >= 10:
            return 429, {"error": "Feedback limit reached for this game."}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                # Escapes also keep unusual Unicode safe in a UTF-8 JSON line.
                stream.write(json.dumps(entry) + "\n")
        except OSError:
            return 500, {"error": "Could not save feedback. Please try again."}
        # Failed writes do not spend the player's allowance.
        game.feedback_count += 1
    return 200, {"ok": True}


def feedback(
    last: Annotated[int | None, typer.Option(min=1, help="Show the newest N entries.")] = None,
) -> None:
    """Print saved feedback, newest first. No model is called."""
    if not DEFAULT_PATH.is_file():
        typer.echo("No feedback saved.")
        return
    entries = DEFAULT_PATH.read_text(encoding="utf-8").splitlines()
    # JSON lines preserve text boundaries and every saved metadata field.
    for line in list(reversed(entries))[:last]:
        typer.echo(line)


def recent(path: Path, count: int = 10) -> list[dict]:
    """Read only the newest entries into memory, newest first."""
    with _LOCK:
        if not path.exists():
            return []
        entries = deque(maxlen=count)
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue  # A damaged or interrupted line must not hide the rest.
                if isinstance(entry, dict):
                    entries.append(entry)
    return list(reversed(entries))
