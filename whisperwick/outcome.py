"""What the world says happened to arrested people. World facts only.

Reads ONLY events (arrest and release). It never reads dialogue text and never the
belief log, so it cannot be swayed by what anyone said or thought. It also never says
whether the right person was held: the murderer is a scenario secret, not a world fact.
"""

from whisperwick import story
from whisperwick.clock import Clock
from whisperwick.events import Event

CUSTODY = ("arrest", "release")


def custody_events(events: list[Event]) -> list[Event]:
    """Arrests and releases, in the order they happened (the log is already in order)."""
    return [e for e in events if e.type in CUSTODY]


def held_at_end(events: list[Event]) -> list[str]:
    """Replay arrests and releases in order. Whoever is still held at the end."""
    held: list[str] = []
    for e in custody_events(events):
        target = e.data["target"]
        if e.type == "arrest" and target not in held:
            held.append(target)
        if e.type == "release" and target in held:
            held.remove(target)
    return held


def event_line(e: Event, names: dict[str, str]) -> str:
    """e.g. 'day 1 09:30  arrest: Hal -> Victor (Town Hall)'. Day first, so days stay apart."""
    who, whom = story.show(names, e.actor), story.show(names, e.data["target"])
    where = story.show(names, e.location)
    line = f"day {Clock(e.tick).day} {story.hhmm(e.tick)}  {e.type}: {who} -> {whom} ({where})"
    # Show the actor's reason too, so "held for obstruction" and "held for murder" differ.
    return f'{line}, saying: "{e.data["reason"]}"' if e.data.get("reason") else line


def last_reasons(events: list[Event]) -> dict[str, str]:
    """For each person still held, the reason given at their latest arrest (if any)."""
    last = {e.data["target"]: e for e in custody_events(events) if e.type == "arrest"}
    return {t: e.data["reason"] for t, e in last.items() if t in held_at_end(events)
            and e.data.get("reason")}  # fmt: skip


def held_text(events: list[Event], names: dict[str, str]) -> str:
    """e.g. 'Victor, Bob' or 'nobody'."""
    held = held_at_end(events)
    return ", ".join(story.show(names, h) for h in held) or "nobody"


def format_outcome(events: list[Event], names: dict[str, str], murderer: str | None = None) -> str:
    """The `outcome` report. `murderer` is only passed when the user asked to see the secret."""
    custody = custody_events(events)
    if not custody:
        out = ["Nobody was arrested."]
    else:
        out = [event_line(e, names) for e in custody]
        out += ["", f"Held at the end: {held_text(events, names)}"]
        # The holder's own words, shown as said. Not checked for truth.
        for who, reason in last_reasons(events).items():
            out.append(f'Reason given for holding {story.show(names, who)}: "{reason}"')
    if murderer:
        # Kept apart and clearly labelled, so it is never mistaken for a world fact.
        out += ["", f"Scenario secret: murderer = {murderer}"]
    return "\n".join(out)
