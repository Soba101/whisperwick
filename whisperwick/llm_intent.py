"""What a villager may choose this turn: exits, people, items, and the JSON schema for it.

Split out of llm_agent.py to keep that file small (#30). Pure functions over the world.
"""

from whisperwick.actions import MAX_MESSAGE_CHARS
from whisperwick.world import World

ACTIONS = ["move", "talk", "look", "take", "drop", "give", "show"]
# Only villagers the scenario names as authority are offered these.
AUTHORITY_ACTIONS = ["arrest", "release"]


def actions_for(world: World, npc_id: str) -> list[str]:
    """The actions this villager may choose: arrest and release only for authority."""
    return [*ACTIONS, *AUTHORITY_ACTIONS] if npc_id in world.authority else list(ACTIONS)


def exits_and_people(world: World, npc_id: str) -> tuple[list[str], list[str]]:
    """Exit location ids from here, and ids of the other NPCs here. Both sorted."""
    here = world.npcs[npc_id].location
    exits = sorted(world.locations[here].links)
    people = [n for n in world.npcs_at(here) if n != npc_id]
    return exits, people


def usable_items(world: World, npc_id: str) -> list[str]:
    """Ids of items on the ground here plus items this NPC holds. Sorted, no repeats."""
    here = world.npcs[npc_id].location
    return sorted({*world.items_at(here), *world.items_held(npc_id)})


def item_lines(world: World, ids: list[str]) -> str:
    """'id (name: description)' for each item, or 'nothing'."""
    return (", ".join(f"{i} ({world.items[i].name}: {world.items[i].description})" for i in ids)
            or "nothing")  # fmt: skip


def intent_schema(world: World, npc_id: str) -> dict:
    """JSON schema for this one turn.

    Target can only be a real exit or a person here, so the model cannot
    write a display name like "Victor" in place of "npc_victor".
    Item can only be an item lying here or one this NPC holds, so no invented objects.
    """
    exits, people = exits_and_people(world, npc_id)
    return {
        "type": "object",
        "properties": {
            "action": {"enum": actions_for(world, npc_id)},
            "target": {"enum": [*exits, *people, None]},
            "item": {"enum": [*usable_items(world, npc_id), None]},
            "message": {"type": ["string", "null"], "maxLength": MAX_MESSAGE_CHARS},
            # A claim is two FLAT fields, not a nested object: llama.cpp grammars
            # handle flat enums better. Each is null unless the words openly do that.
            "accuses": {"enum": [*sorted(world.npcs), None]},
            "defends": {"enum": [*sorted(world.npcs), None]},
        },
        "required": ["action", "target", "item", "message", "accuses", "defends"],
        "additionalProperties": False,
    }
