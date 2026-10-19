"""Render starting observations from ground truth; never expose secret records to agents."""

from whisperwick.crime.pools import CLUES, MEMORIES
from whisperwick.items import Item


def context(sc):
    secret = sc.secrets
    people = {n.id: f"{n.name} ({n.id})" for n in sc.npcs}
    places = {p.id: f"{p.name} ({p.id})" for p in sc.locations}
    return dict(
        killer=people[secret["murderer"]],
        victim=people[secret["victim"]],
        innocent=people[secret["innocent"]],
        place=places[secret["place"]],
        weapon=secret["weapon"],
        motive=secret["motive"],
        hour=f"{secret['hour']:02d}",
    )


def clues(sc):
    """Items and witness lines are separate, inspectable evidence sources."""
    c = context(sc)
    s = sc.secrets
    items = [
        Item(
            id="item_crime_weapon",
            name=f"bloodied {s['weapon']}",
            description=CLUES["weapon"].format(**c),
            location=s["place"],
        ),
        Item(
            id="item_crime_cuff",
            name="bloodstained cuff",
            description=CLUES["trace"].format(**c),
            holder=s["murderer"],
        ),
    ]
    lines = [
        (s["witness"], CLUES["sighting"].format(**c)),
        ("npc_hal", MEMORIES["discovery"].format(**c)),
    ]
    # Both observations are true, but neither describes the killing.
    for key in s["misleading"]:
        lines.append((s["witness"], CLUES[key].format(**c)))
    return items, lines


def private_memories(sc):
    c = context(sc)
    s = sc.secrets
    lines = [
        (s["murderer"], MEMORIES["killer"].format(**c)),
        (s["murderer"], MEMORIES["ownership"].format(**c)),
    ]
    if s["accomplice"]:
        lines.append((s["accomplice"], MEMORIES["accomplice"].format(**c)))
    return lines
