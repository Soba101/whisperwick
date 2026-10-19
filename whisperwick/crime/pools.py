"""Fixed starting-fact pools. No template gives an agent a plan."""

from pathlib import Path

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"
CAST = ("npc_alice", "npc_bob", "npc_sarah", "npc_victor", "npc_hal", "npc_mayor")
CANDIDATES = tuple(n for n in CAST if n != "npc_hal")
PLACES = ("loc_inn", "loc_market", "loc_temple", "loc_town_hall")
HOURS = (21, 22, 23, 0, 1, 2)
MOTIVES = (
    "an unpaid debt",
    "jealousy over a lost friendship",
    "a secret about to come out",
    "a disputed inheritance",
    "revenge for a broken agreement",
)
WEAPONS = ("knife", "rope", "candlestick", "poisoned mug")
TEMPERAMENTS = (
    "Warm and talkative.",
    "Quiet and patient.",
    "Blunt and proud.",
    "Cheerful and restless.",
    "Reserved and meticulous.",
    "Quick-tempered.",
)
RELATIONS = (
    "{other} owes me money for repairs.",
    "I owe {other} money for supplies.",
    "{other} broke an agreement with me last winter.",
)
WISHES = (
    "I have long wished to buy the inn.",
    "I have long wished to travel to the coast.",
    "I have long wished to pay off my debts.",
    "I have long wished to own a garden.",
)
STRANGERS = (
    "Usually shy with strangers.",
    "Usually welcoming to strangers.",
    "Usually formal with strangers.",
    "Usually curious about strangers.",
)
# Physical traces and a separate sighting have different sources.
CLUES = {
    "weapon": "A {weapon} with dried blood and {killer}'s engraved initials.",
    "trace": "{killer}'s cuff, stained with {victim}'s blood from last night.",
    "sighting": "Last night at {hour}:00 I saw {killer} leaving {place} carrying a {weapon}.",
    "quarrel": "Yesterday I heard {innocent} quarrel with {victim} over a bill.",
    "visit": "Yesterday afternoon I saw {innocent} enter {place} to deliver supplies.",
}
MEMORIES = {
    "killer": (
        "Last night at {hour}:00 I killed {victim} in {place} with a {weapon}, over {motive}."
    ),
    "accomplice": (
        "Last night I helped {killer} conceal the killing of {victim} by washing the floor."
    ),
    "discovery": "At dawn I found {victim} dead in {place}.",
    "ownership": "The initials engraved on my {weapon} are mine.",
}
