"""The thought schema and its limits. Split out of thinking.py to keep that file small."""

from whisperwick import aims
from whisperwick.thought_people import people_ids

THOUGHTS_MAX_CHARS = 400  # a thought is a few sentences, never an essay
WHY_MAX_CHARS = 150
OF_WHAT_MAX_CHARS = 100  # e.g. "killing the mayor", in the villager's own words
MAX_BECAUSE = 5
MAX_TRUST = 6
SURENESS = ["unsure", "fairly sure", "certain"]
LEVELS = ["low", "medium", "high"]


def schema(world, npc_id: str, memory_ids: list[str]) -> dict:
    """Enums everywhere, so the model can only name real people and memories it was shown."""
    suspects, trusted = people_ids(world, npc_id)
    return {
        "type": "object",
        "properties": {
            "thoughts": {"type": "string", "maxLength": THOUGHTS_MAX_CHARS},
            # Who they truly believe did it (their private belief).
            "suspect": {"enum": [*suspects, None]},
            # What they suspect that person of, in their own words. The code never names a crime:
            # a villager only knows about the murder if it saw the body or was told.
            "of_what": {"type": ["string", "null"], "maxLength": OF_WHAT_MAX_CHARS},
            "sureness": {"enum": SURENESS},
            # Who they mean to accuse out loud, if anyone. May differ from suspect: that is
            # how belief and intention are recorded apart. Only living others can be named.
            "will_accuse": {"enum": [*trusted, None]},
            # What they want to do next, in their own words (see aims.py). May be null.
            **aims.schema_properties(),
            "because": {"type": "array", "maxItems": MAX_BECAUSE, "items": {"enum": memory_ids}},
            "trust": {
                "type": "array",
                "maxItems": MAX_TRUST,
                "items": {
                    "type": "object",
                    "properties": {
                        "person": {"enum": trusted},
                        "level": {"enum": LEVELS},
                        "why": {"type": "string", "maxLength": WHY_MAX_CHARS},
                    },
                    "required": ["person", "level", "why"],
                },
            },
        },
        "required": [
            "thoughts", "suspect", "of_what", "sureness", "will_accuse", "aim", "aim_status",
            "because", "trust",
        ],  # fmt: skip
    }
