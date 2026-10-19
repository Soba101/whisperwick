"""Player-only scene prose. Nothing here changes the world or supplies a prompt."""

import random

from whisperwick.player import PLAYER_ID


def time_of_day(tick: int) -> str:
    """Use the same words each day. One tick is one minute."""
    hour = tick % 1440 // 60
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 14:
        return "midday"
    if 14 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "night"


def scene(world, observation: dict, seed: int, observer: str = PLAYER_ID) -> str:
    """Describe only the look, the clock and witnessed actions of people in the look.

    Names are display labels only. All membership checks use stable ids.
    A private RNG keeps presentation from changing any future engine choice.
    """
    tick = world.clock.tick
    rng = random.Random(f"{seed}:{tick}")

    def choose(*templates, **facts):
        return rng.choice(templates).format(**facts)

    def names(ids, table):
        return ", ".join(table[i].name for i in sorted(ids))

    here = observation["location"]
    parts = [choose("{time} at {place}.", "It is {lower} at {place}.",
                    time=time_of_day(tick).capitalize(), lower=time_of_day(tick),
                    place=world.locations[here].name)]
    # Read only witnessed history. An unseen action must never displace a visible one.
    latest = {}
    for event in world.log.all():
        if event.tick <= tick and observer in event.witnesses:
            latest[event.actor] = event
    for person in sorted(observation["people"]):
        who = world.npcs[person].name
        event = latest.get(person)
        action = _action(event, here)
        if action:
            # Past wording avoids claiming an old action is still happening now.
            parts.append(choose("{who} is here, last seen {action}.",
                                "{who} is here; you last saw them {action}.",
                                who=who, action=action))
        else:
            parts.append(choose("{who} is here.", "You see {who} here.", who=who))
        if person in observation.get("held", []):
            parts.append(choose("{who} is held in custody.", "{who} is in custody.", who=who))
    for body in sorted(observation["bodies"]):
        parts.append(choose("{who}'s body lies here.", "You see the body of {who} here.",
                            who=world.npcs[body].name))
    if observation["items"]:
        parts.append(choose("On the ground: {items}.", "You see {items} on the ground.",
                            items=names(observation["items"], world.items)))
    if observation["exits"]:
        parts.append(choose("Open ways lead to {places}.", "The ways to {places} are open.",
                            places=names(observation["exits"], world.locations)))
    else:
        parts.append(choose("There are no ways out.", "No way leads out of here."))
    return " ".join(parts)


def _action(event, here: str) -> str | None:
    """Only describe supported events at this place. Never invent occupational work."""
    if event is None or event.location != here:
        return None
    # Item names and recipients may be out of sight now. Describe only the gesture.
    return {
        "move": "arriving here",
        "talk": "speaking",
        "take": "picking something up",
        "drop": "putting something down",
        "give": "handing something over",
        "show": "showing an item",
        "use": "using an item",
        "arrest": "making an arrest",
        "release": "releasing someone from custody",
    }.get(event.type)
