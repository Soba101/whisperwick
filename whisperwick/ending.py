"""Player-only ending, calculated from events and saved truth. No model calls."""

from whisperwick import outcome, story
from whisperwick.events import Event
from whisperwick.player import PLAYER_ID


def report(events: list[Event], names: dict[str, str], secrets: dict,
           authority: list[str], accusation: dict | None = None,
           title: str | None = None) -> str:
    murderer = secrets.get("murderer")
    victim = secrets.get("victim")
    truth = (f"{story.show(names, murderer)} killed {story.show(names, victim)}."
             if murderer and victim else "Truth unavailable in this run.")
    # Replay all custody events before filtering by holder. A later release matters.
    held = {}
    for event in outcome.custody_events(events):
        target = event.data["target"]
        if event.type == "arrest":
            held[target] = event.actor
        else:
            held.pop(target, None)
    lines = [f"Your role: {title}."] if title else []
    lines.append(f"The truth: {truth}")
    for holder in authority:
        holding = ", ".join(story.show(names, n) for n, h in held.items() if h == holder)
        lines.append(f"{story.show(names, holder)} holds at the end: {holding or 'nobody'}.")
    lines += [outcome.event_line(e, names) for e in events
              if e.type == "arrest" and e.actor in authority]
    target = accusation.get("target") if accusation else None
    if accusation is None:
        verdict = "No accusation recorded."
    elif target is None:
        verdict = "You named nobody."
    else:
        correct = "right" if target == murderer else "wrong" if murderer else "truth unavailable"
        verdict = f"You accused {story.show(names, target)} ({correct})."
    lines += [f"Your accusation: {verdict}", "Your side:", verdict]
    # Count only successful engine events. Talk does not prove a warning was given.
    for kind in ("give", "show") if murderer else ():
        count = sum(e.actor == PLAYER_ID and e.type == kind and
                    (e.data.get("to") == murderer or
                     kind == "show" and not e.data.get("to") and murderer in e.witnesses)
                    for e in events)
        label = f"{'Gives' if kind == 'give' else 'Shows'} to {story.show(names, murderer)}"
        lines.append(f"{label}: {count}.")
    return "\n".join(lines)
