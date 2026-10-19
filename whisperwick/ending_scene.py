"""Fixed ending templates. This is a private view, never a world event."""

from collections import Counter

from whisperwick import outcome, story
from whisperwick.clock import Clock
from whisperwick.player import PLAYER_ID


def account(events, names, secrets, victim_place=None):
    """Use saved truth. Dialogue is never evidence for the account."""
    killer, victim = secrets.get("murderer"), secrets.get("victim")
    if not killer or not victim:
        return "Truth unavailable in this run."
    # Old scenarios start after the death. Their body supplies the place only.
    death = next((e for e in events if e.type in ("kill", "murder")
                  and e.actor == killer and e.data.get("target") == victim), None)
    # Generated crimes (week 14) save the place as "place", plus the hour and motive.
    place = (secrets.get("location") or secrets.get("place")
             or (death.location if death else victim_place))
    hour = secrets.get("hour")
    # "Last night at 00:00" reads oddly; midnight gets its own words.
    if isinstance(hour, int):
        text = "Just after midnight, " if hour == 0 else f"Last night at {hour:02d}:00, "
    else:
        text = ""
    text += f"{story.show(names, killer)} killed {story.show(names, victim)}"
    if place:
        text += f" in {story.show(names, place)}"
    # Do not infer a weapon from a wound, clue, or a villager's words.
    if weapon := secrets.get("weapon"):
        text += f" with the {story.show(names, weapon)}"
    if motive := secrets.get("motive"):
        text += f", over {motive}"
    text += "."
    text = text[0].upper() + text[1:]
    if accomplice := secrets.get("accomplice"):
        text += f" {story.show(names, accomplice)} was an accomplice."
    return text


def scene(sc, events, accusation):
    """Only called after the private accusation is recorded."""
    names = story.names_from(sc)
    killer, victim = sc.secrets.get("murderer"), sc.secrets.get("victim")
    body = next((n for n in sc.npcs if n.id == victim), None)
    held = {n.id: n.held_by for n in sc.npcs if n.held_by}
    places = {n.id: n.location for n in sc.npcs}
    timeline = []
    for e in events:
        if e.type == "move":
            places[e.actor] = e.data["to"]
        if e.type not in outcome.CUSTODY:
            continue
        target = e.data["target"]
        if e.type == "arrest":
            held[target] = e.actor
        else:
            held.pop(target, None)
        if e.actor in sc.authority:
            timeline.append({"type": e.type, "actor": e.actor, "target": target,
                             "time": Clock(e.tick).label(),
                             "text": outcome.event_line(e, names),
                             "words": e.data.get("reason", "")})
    target = accusation["target"]
    verdict = (f"You accused {story.show(names, target)} "
               f"({'right' if target == killer else 'wrong' if killer else 'truth unavailable'})."
               if target else "You named nobody.")
    talks = Counter(e.data["to"] for e in events
                    if e.type == "talk" and e.actor == PLAYER_ID and e.data.get("to"))
    side = []
    # Counts record physical acts, without guessing loyalty or intent.
    for kind, label in (("give", "Gives"), ("show", "Shows")) if killer else ():
        count = sum(e.actor == PLAYER_ID and e.type == kind and
                    (e.data.get("to") == killer or kind == "show" and
                     not e.data.get("to") and killer in e.witnesses) for e in events)
        side.append(f"{label} to {story.show(names, killer)}: {count}.")
    # End-scene figures are revealed facts. No private inventories are included.
    figures = [{"id": n.id, "name": n.name, "place": places[n.id],
                "held": n.id in held, "holder": held.get(n.id), "body": not n.alive}
               for n in sc.npcs if n.id == killer or held.get(n.id) in sc.authority]
    return {"account": account(events, names, sc.secrets, body.location if body else None),
            "timeline": timeline, "custody": [
                f"{story.show(names, h)} holds at the end: " +
                (", ".join(story.show(names, n) for n in held if held[n] == h) or "nobody") + "."
                for h in sc.authority],
            "role": sc.player_title or "Wren, newcomer", "accusation": verdict,
            "accusation_correct": target == killer if target and killer else None,
            "side": side, "talks": [{"id": n, "name": story.show(names, n), "count": talks[n]}
                                     for n in sorted(talks)],
            "killer": killer, "people": figures}
