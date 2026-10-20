"""Conversation text built only from facts both speakers can know."""

from whisperwick.act_prompt import people_label
from whisperwick.belief_text import character_lines
from whisperwick.memory_text import describe


def build_schema(a, b):
    """Limit speaker ids to this pair, regardless of who lives in the world."""
    # Bound the reply so one call cannot take over a long stretch of conversation.
    return {
        "type": "object", "additionalProperties": False, "required": ["lines"],
        "properties": {"lines": {"type": "array", "minItems": 1, "maxItems": 3,
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["speaker", "message"], "properties": {
                          "speaker": {"type": "string", "enum": [a, b]},
                          "message": {"type": "string"}}}}},
    }


def build_messages(world, a, b, personalities):
    """Read event ids from the log, never either speaker's private memory text."""
    # Shared surroundings let both speakers refer to the same place and people.
    here = world.locations[world.npcs[a].location]
    lines = [
        "Write the next lines of this conversation in the given speaker order.",
        "Each line is what that person would say, using only the facts listed.",
        "Fewer lines are fine if the conversation would end. Reply only with JSON.",
        # Explicit slots keep each voice tied to its intended recipient.
        *[f"Line {i}: {people_label(world, speaker)} to {target}"
          for i, (speaker, target) in enumerate(((a, b), (b, a), (a, b)), 1)],
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
    # A multi-step event can have different audiences for each piece.
    shared = [e.model_copy(update={"data": {**e.data, "steps": [
        r for r in e.data["steps"] if {a, b} <= {e.actor, *r["witnesses"]}
    ]}}) if "steps" in e.data else e for e in shared]
    lines.append("Shared events:")
    # Recent shared events keep the prompt small as the world log grows.
    lines.extend(f"Event {e.id}: {describe(e, world, None)}" for e in shared[-20:])
    return [{"role": "system", "content": "\n".join(lines)},
            {"role": "user", "content": "What are the next conversation lines?"}]


def parse_lines(reply, a, b):
    """Check the actual reply too; fake or remote clients can ignore a schema."""
    # Extra fields could hide an unexpected reply shape from the queue.
    if not isinstance(reply, dict) or set(reply) != {"lines"}:
        raise ValueError("exchange reply must contain only lines")
    lines = reply["lines"]
    # Enforce the same turn limit even when schema validation was skipped.
    if not isinstance(lines, list) or not 1 <= len(lines) <= 3:
        raise ValueError("exchange needs one to three lines")
    # Check types before trimming so malformed replies fail with a clear reason.
    if any(not isinstance(line, dict) or set(line) != {"speaker", "message"}
           or not isinstance(line["speaker"], str) or not isinstance(line["message"], str)
           for line in lines):
        raise ValueError("exchange lines need speaker and message strings")
    cleaned = []
    for line, speaker in zip(lines, (a, b, a), strict=False):
        # Later speech may rely on this slot, so keep only an unbroken valid prefix.
        if line["speaker"] != speaker:
            return cleaned, "wrong speaker"
        message = line["message"].strip()
        # Empty speech ends this slot; removing it would shift the speaker order.
        if not message:
            return cleaned, "blank"
        cleaned.append(message)
    return cleaned, None
