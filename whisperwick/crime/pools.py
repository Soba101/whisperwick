"""Fixed starting-fact pools. No template gives an agent a plan."""

from pathlib import Path

# Re-export the pools so callers have one small entry point.
from whisperwick.crime.character_pools import RELATIONS, STRANGERS, TEMPERAMENTS, WISHES
from whisperwick.crime.evidence_pools import ACCOMPLICE_JOBS, CLUES, MEMORIES, MISLEADING

__all__ = [
    "RELATIONS", "STRANGERS", "TEMPERAMENTS", "WISHES", "ACCOMPLICE_JOBS",
    "CLUES", "MEMORIES", "MISLEADING",
]

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
    "blackmail",
    "a secret love affair",
    "a land dispute",
    "covering up a theft",
    "a ruined business deal",
    "an old family feud",
    "a forged will",
)
# Every weapon becomes a real item. Poison leaves residue rather than blood.
WEAPONS = {
    "knife": ("A sharp kitchen knife", "dried blood on its blade"),
    "rope": ("A length of rough hemp rope", "a tightened loop and fibres from {victim}'s collar"),
    "candlestick": ("A brass candlestick", "dried blood on its dented base"),
    "poisoned mug": ("A glazed drinking mug", "poison residue in the dregs"),
    "hammer": ("An iron carpenter's hammer", "dried blood on its head"),
    "vial of poison": ("A small glass vial", "a few drops of poison under its stopper"),
    "fire poker": ("An iron fire poker", "dried blood on its pointed end"),
    "heavy ledger box": ("A heavy oak ledger box", "dried blood on its brass corner"),
}
