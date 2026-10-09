"""Repeat guard (issue #12): stop NPCs from showing, giving or saying the same thing again.

Agent side only, like memories and the belief log. It is never part of World state or state_hash.
One ActionHistory is made per run. The engine still decides what is legal;
this only refuses a pointless repeat BEFORE World.act, with a reason the model can read.
"""

from dataclasses import dataclass

from whisperwick.actions import Intent
from whisperwick.clock import Clock

# How long a repeat counts, in game minutes (2 hours). Exactly this long later is allowed again.
REPEAT_WINDOW = 120


@dataclass
class Record:
    """One thing an NPC did. Ids only, no display names."""

    tick: int
    actor: str
    action: str
    target: str | None
    item: str | None
    claim: tuple[str, str] | None  # (kind, subject)
    message: str | None


def normalise(message: str | None) -> str:
    """Lowercase and collapse spaces, so 'Hi  there' and 'hi there' count as the same."""
    return " ".join((message or "").lower().split())


def record_of(tick: int, intent: Intent) -> Record:
    claim = (intent.claim.kind, intent.claim.subject) if intent.claim else None
    return Record(tick, intent.actor, intent.action, intent.target, intent.item, claim,
                  intent.message)  # fmt: skip


def is_repeat(old: Record, new: Record) -> bool:
    """Is `new` the same act as `old`? (Same actor and window are checked by the caller.)"""
    if old.action != new.action:
        return False
    if new.action in ("show", "give"):  # same item to the same audience (None = everyone here)
        return old.item == new.item and old.target == new.target
    if new.action == "talk":
        # Only the exact same words count. The same claim in new words is harmless:
        # the hearer already got that claim from this teller.
        if old.target != new.target:
            return False
        return normalise(old.message) == normalise(new.message)
    return False  # moving, looking and taking can be repeated freely


class ActionHistory:
    """Every successful NPC intent of this run, in order."""

    def __init__(self):
        self.records: list[Record] = []

    def record(self, tick: int, intent: Intent) -> None:
        self.records.append(record_of(tick, intent))

    def find_repeat(self, tick: int, intent: Intent) -> Record | None:
        """The earlier record this intent repeats inside the window, or None."""
        new = record_of(tick, intent)
        for old in reversed(self.records):
            if old.actor == new.actor and tick - old.tick < REPEAT_WINDOW and is_repeat(old, new):
                return old
        return None

    def recent_to(self, actor: str, people: list[str], n: int = 3) -> list[Record]:
        """The actor's last n talks, shows and gives aimed at these people (or at everyone)."""
        spoken = [
            r
            for r in self.records
            if r.actor == actor
            and r.action in ("talk", "show", "give")
            and (r.target in people or (r.target is None and r.action == "show"))
        ]
        return spoken[-n:]


def repeat_reason(world, history: ActionHistory, intent: Intent) -> str | None:
    """Feedback for the model if this intent is a repeat, else None."""
    old = history.find_repeat(world.clock.tick, intent)
    if old is None:
        return None
    when = Clock(old.tick).label()
    who = "everyone here" if old.target is None else f"{world.npcs[old.target].name} ({old.target})"
    item = world.items[old.item].name if old.item in world.items else old.item
    if old.action == "show":
        what = f"showed {item} to {who}"
    elif old.action == "give":
        what = f"gave {item} to {who}"
    else:
        what = f"said that to {who}"
    return f"you already {what} at {when}; do something new"
