"""Render starting observations from ground truth; never expose secret records to agents."""

from whisperwick.crime import pools
from whisperwick.items import Item


def context(sc):
    secret = sc.secrets
    people = {n.id: f"{n.name} ({n.id})" for n in sc.npcs}
    places = {p.id: f"{p.name} ({p.id})" for p in sc.locations}
    c = dict(
        killer=people[secret["murderer"]],
        victim=people[secret["victim"]],
        accomplice=people.get(secret["accomplice"]),
        innocent=people[secret["innocent"]],
        place=places[secret["place"]],
        weapon_place=places[secret["weapon_place"]],
        trail_place=places[secret["trail_place"]],
        weapon=secret["weapon"],
        motive=secret["motive"],
        hour=f"{secret['hour']:02d}",
    )
    description, trace = pools.WEAPONS[secret["weapon"]]
    c["weapon_clue"] = (
        f"{description} with {trace} and {{killer}}'s engraved initials."
    ).format(**c)
    return c


# The source is explicit: two recollections by one witness count only once.
ITEM_CLUES = {
    "trace": ("cuff", "bloodstained cuff", "killer"),
    "scrap": ("scrap", "torn coat scrap", "scene"),
    "mud": ("footprints", "footprint cast", "scene"),
    "possession": ("locket", "victim's silver locket", "killer"),
    "letter": ("letter", "handwritten meeting note", "scene"),
}


def clue_sources(sc):
    return {
        f"item:{key}" if key in ITEM_CLUES or key == "weapon"
        else f"witness:{sc.secrets['witness']}"
        for key in sc.secrets["clues"]
    }


def clues(sc):
    """Items and witness lines are separate, inspectable evidence sources."""
    c = context(sc)
    s = sc.secrets
    items = [Item(
        id="item_crime_weapon", name=s["weapon"],
        description=c["weapon_clue"], location=s["weapon_place"],
    )]
    lines = [("npc_hal", pools.MEMORIES["discovery"].format(**c))]
    for key in s["clues"]:
        if key == "weapon":
            continue
        text = pools.CLUES[key].format(**c)
        if key in ITEM_CLUES:
            suffix, name, placement = ITEM_CLUES[key]
            items.append(Item(
                id=f"item_crime_{suffix}", name=name, description=text,
                holder=s["murderer"] if placement == "killer" else None,
                location=s["place"] if placement == "scene" else None,
            ))
        else:
            lines.append((s["witness"], text))
    if s["accomplice"]:
        job = s["accomplice_job"]
        _, clue = pools.ACCOMPLICE_JOBS[job]
        if job in ("washed_floor", "carried_item"):
            items.append(Item(
                id="item_crime_accomplice", name="bloodied rag" if job == "washed_floor"
                else "bloodied cloth", description=clue.format(**c),
                holder=s["accomplice"] if job == "carried_item" else None,
                location=s["place"] if job == "washed_floor" else None,
            ))
        elif clue:
            lines.append((s["witness"], clue.format(**c)))
    # Both observations are true, but neither describes the killing.
    for key in s["misleading"]:
        lines.append((s["witness"], pools.MISLEADING[key].format(**c)))
    return items, lines


def private_memories(sc):
    c = context(sc)
    s = sc.secrets
    lines = [
        (s["murderer"], pools.MEMORIES["killer"].format(**c)),
        (s["murderer"], pools.MEMORIES["ownership"].format(**c)),
    ]
    if "mud" in s["clues"]:
        lines.append((s["murderer"], pools.MEMORIES["trail"].format(**c)))
    if s["accomplice"]:
        memory, _ = pools.ACCOMPLICE_JOBS[s["accomplice_job"]]
        lines.append((s["accomplice"], memory.format(**c)))
    return lines
