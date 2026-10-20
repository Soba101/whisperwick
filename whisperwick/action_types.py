"""Intent data and action results. These contain no world-changing code."""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from whisperwick.events import Event

# Longest thing an NPC may say in one turn. Stops runaway LLM output later.
MAX_MESSAGE_CHARS = 500

# What a claim can say about a person. The one place to add a new kind.
CLAIM_KINDS = ("accuses", "defends")


class Claim(BaseModel):
    """A structured statement about one person, carried by a talk.

    Only claims (never free text) will change beliefs, so they must be well formed.
    The kind and subject are checked by the engine in claims.py, not here, so a bad
    one becomes a clear rejection reason instead of a parse error.
    """

    model_config = ConfigDict(extra="forbid")

    kind: str  # one of CLAIM_KINDS
    subject: str  # a person id, e.g. "npc_hal"


class Intent(BaseModel):
    """One proposed action. Week 2's JSON schema for the LLM is built from this."""

    # Reject unknown fields. A model inventing fields is a bug we want to see.
    model_config = ConfigDict(extra="forbid")

    actor: str  # who wants to act, e.g. "npc_bob"
    # "move" | "talk" | "look" | "take" | "drop" | "give" | "show" | "use" | "arrest" | "release"
    action: str
    # A location id (move) or an npc id (talk, give, show, arrest, release).
    target: str | None = None
    message: str | None = None  # what to say (talk), or the reason (arrest, release)
    item: str | None = None  # an item id (take, drop, give, show, use)
    claim: Claim | None = None  # "accuses X" or "defends X" (talk only)
    text: str | None = None  # a gesture, checked by the engine
    name: str | None = None  # the proposed action's stable name
    params: list[str] | None = None
    needs: list[str] | None = None
    does: list[str] | None = None
    use: dict[str, str] | None = None  # optional immediate arguments for make
    person: str | None = None  # made actions use explicit parameter names
    exit: str | None = None


@dataclass
class ActionResult:
    """What the engine tells the agent after it tries something."""

    ok: bool
    reason: str = ""  # why it failed, in plain words (agents will read this)
    event: Event | None = None  # the event that was logged, if it changed the world
    observation: dict[str, Any] | None = None  # what the agent sees (look only)


def reject(reason: str) -> ActionResult:
    return ActionResult(False, reason)

