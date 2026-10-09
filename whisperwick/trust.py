"""Trust: how much one person believes another's claims. Agent side only.

Never part of World state or state_hash. Deterministic: same events, same numbers.
"""

# How far trust moves when a claim clashes with, or matches, what I saw myself.
TRUST_DROP = 0.15
TRUST_RISE = 0.05


def clamp(x: float) -> float:
    """Keep a number in 0..1 and round it, so floats stay stable across runs."""
    return round(min(1.0, max(0.0, x)), 4)


class Trust:
    """trust[holder][other] in 0..1. Pairs nobody changed use the scenario defaults."""

    def __init__(self, default: float = 0.5, player: float = 0.3, player_id: str = "player"):
        self.default, self.player, self.player_id = default, player, player_id
        self.pairs: dict[str, dict[str, float]] = {}  # only pairs that changed

    @classmethod
    def from_scenario(cls, scenario) -> "Trust":
        from whisperwick.player import PLAYER_ID

        t = scenario.trust
        return cls(t.get("default", 0.5), t.get("player", 0.3), PLAYER_ID)

    def get(self, holder: str, other: str) -> float:
        """How much holder trusts other. The player is a stranger, so lower by default."""
        stored = self.pairs.get(holder, {}).get(other)
        if stored is not None:
            return stored
        return self.player if other == self.player_id else self.default

    def change(self, holder: str, other: str, delta: float) -> None:
        self.pairs.setdefault(holder, {})[other] = clamp(self.get(holder, other) + delta)

    def to_dict(self) -> dict:
        return {
            "default": self.default,
            "player": self.player,
            "player_id": self.player_id,
            "pairs": {h: dict(sorted(p.items())) for h, p in sorted(self.pairs.items())},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Trust":
        t = cls(d["default"], d["player"], d["player_id"])
        t.pairs = {h: dict(p) for h, p in d["pairs"].items()}
        return t
