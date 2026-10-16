"""Conversation text built only from facts both speakers can know."""

from whisperwick.act_prompt import people_label
from whisperwick.belief_text import character_lines
from whisperwick.memory_text import describe

# Bound the reply so one call cannot take over a long stretch of conversation.
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["lines"],
    "properties": {"lines": {"type": "array", "minItems": 1, "maxItems": 3,
                              "items": {"type": "string"}}},
}


def build_messages(world, a, b, personalities):
    """Read event ids from the log, never either speaker's private memory text."""
    # Shared surroundings let both speakers refer to the same place and people.
    here = world.locations[world.npcs[a].location]
    lines = [
        "Write the next lines of this conversation in the given speaker order.",
        "Each line is what that person would say, using only the facts listed.",
        "Fewer lines are fine if the conversation would end. Reply only with JSON.",
        f"Speaker order: {a}, {b}, {a}.",
        f"Time: {world.clock.label()}.",
        f"Place: {here.id} ({here.name}).",
        "People here: " + ", ".join(people_label(world, p) for p in world.npcs_at(here.id)),
    ]
    # Personality shapes the voice without adding private memories to shared facts.
    for npc in (a, b):
        lines.append(f"Speaker: {people_label(world, npc)}.")
        lines.extend(character_lines(personalities.get(npc)))
    # Participation is enough; actors are deliberately absent from their witness list.
    shared = [e for e in world.log.all()
              if {a, b} <= {e.actor, *e.witnesses}]
    lines.append("Shared events:")
    # Recent shared events keep the prompt small as the world log grows.
    lines.extend(f"Event {e.id}: {describe(e, world, None)}" for e in shared[-20:])
    return [{"role": "system", "content": "\n".join(lines)},
            {"role": "user", "content": "What are the next conversation lines?"}]


def parse_lines(reply):
    """Check the actual reply too; fake or remote clients can ignore a schema."""
    # Extra fields could hide an unexpected reply shape from the queue.
    if not isinstance(reply, dict) or set(reply) != {"lines"}:
        raise ValueError("exchange reply must contain only lines")
    lines = reply["lines"]
    # Enforce the same turn limit even when schema validation was skipped.
    if not isinstance(lines, list) or not 1 <= len(lines) <= 3:
        raise ValueError("exchange needs one to three lines")
    # Check types before trimming so malformed replies fail with a clear reason.
    if any(not isinstance(line, str) for line in lines):
        raise ValueError("exchange lines must be strings")
    # Empty speech must not consume a speaker's turn.
    cleaned = [line.strip() for line in lines if line.strip()]
    if not cleaned:
        raise ValueError("exchange lines are blank")
    return cleaned
