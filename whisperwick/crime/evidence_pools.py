"""Evidence templates describe objects or remembered observations only."""

# Physical traces and a separate sighting have different sources.
CLUES = {
    "weapon": "{weapon_clue}",
    "trace": "{killer}'s cuff, stained with {victim}'s blood from last night.",
    "sighting": "Last night at {hour}:00 I saw {killer} leaving {place} carrying a {weapon}.",
    "scrap": "A torn scrap caught on a nail in {place}; it fits the tear in {killer}'s coat.",
    "mud": (
        "A cast of footprints at {place}, with the broken heel pattern of {killer}'s boots "
        "and clay from {trail_place}."
    ),
    "possession": "{victim}'s silver locket, now in {killer}'s pocket.",
    "quarrel": "Last night at {hour}:00 I heard {killer} and {victim} quarrelling in {place}.",
    "letter": "A note in {killer}'s handwriting to {victim}: Meet me at {place} at {hour}:00.",
}
MISLEADING = {
    "quarrel": "Yesterday I heard {innocent} quarrel with {victim} over a bill.",
    "visit": "Yesterday afternoon I saw {innocent} enter {place} to deliver supplies.",
    "debt": "Yesterday {victim} told {innocent} that their debt was overdue.",
    "threat": "Last week I heard {innocent} threaten to ruin {victim}'s trade.",
    "lost_knife": "Yesterday {innocent} told me they had lost their kitchen knife.",
}
# Each job records participation, not advice on what to say or do next.
ACCOMPLICE_JOBS = {
    "washed_floor": (
        "Last night I helped {killer} conceal the killing of {victim} by washing the floor.",
        "A floor rag with {victim}'s blood and {accomplice}'s stitched initials.",
    ),
    "hid_weapon": (
        "Last night I helped {killer} conceal the killing of {victim} by hiding the "
        "{weapon} in {weapon_place}.",
        "Last night I saw {accomplice} put the {weapon} in {weapon_place} after "
        "coming from {place}.",
    ),
    "false_alibi": (
        "After {killer} killed {victim}, I agreed with {killer} to say we were together "
        "at {hour}:00 last night.",
        None,
    ),
    "kept_watch": (
        "Last night I kept watch at the door of {place} while {killer} killed {victim} inside.",
        "Last night at {hour}:00 I saw {accomplice} watching the door of {place} "
        "while {killer} was inside.",
    ),
    "carried_item": (
        "Last night I carried away a cloth stained with {victim}'s blood after "
        "helping {killer} conceal the killing.",
        "A cloth stained with {victim}'s blood, carried away by {accomplice} last night.",
    ),
}
MEMORIES = {
    "killer": (
        "Last night at {hour}:00 I killed {victim} in {place} with a {weapon}, over {motive}."
    ),
    "discovery": "At dawn I found {victim} dead in {place}.",
    "ownership": "The initials engraved on my {weapon} are mine.",
    "trail": "Last night before {hour}:00 I walked through the clay at {trail_place}.",
}
