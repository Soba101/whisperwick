"""What the web page may show. Pure functions over the world, nothing is changed.

Everything here is limited to what Wren can see from where she stands: the people and
items at her place, what she carries, her exits. No beliefs, no thoughts, no secret,
and nobody from another place. The map shows places only.
"""

from whisperwick import outcome, story
from whisperwick.player import PLAYER_ID
from whisperwick.replay_state import layout
from whisperwick.scenario import Scenario
from whisperwick.web_icons import ACTION_ICONS, PLACE_ICONS
from whisperwick.world import World


def named(table: dict, ids: list[str]) -> list[dict]:
    """[{id, name}] for ids found in a table of locations, items or npcs."""
    return [{"id": i, "name": table[i].name} for i in ids]


def map_data(sc: Scenario) -> list[dict]:
    """Every place with a fixed spot and its links. Same layout as the replay page."""
    spots = layout(sc)
    return [
        {"id": p.id, "name": p.name, "x": spots[p.id][0], "y": spots[p.id][1], "links": p.links,
         "icon": PLACE_ICONS.get(p.id, "•")}
        for p in sc.locations
    ]


def you_view(world: World) -> dict:
    """Wren's own view: time, place, people and bodies here, items here and carried."""
    here = world.npcs[PLAYER_ID].location
    others = [n for n in world.npcs_at(here) if n != PLAYER_ID]
    return {
        "clock": world.clock.label(),
        "place": {"id": here, "name": world.locations[here].name},
        "people": [
            {"id": n, "name": world.npcs[n].name, "occupation": world.npcs[n].occupation,
             "held": world.npcs[n].held_by is not None}
            for n in others
        ],  # fmt: skip
        "bodies": named(world.npcs, world.bodies_at(here)),
        "ground": named(world.items, world.items_at(here)),
        "carried": named(world.items, world.items_held(PLAYER_ID)),
        "exits": named(world.locations, sorted(world.locations[here].links)),
    }


def actions_for(view: dict) -> list[dict]:
    """All seven actions, their choices, and a reason when they cannot be tried.

    Authority actions (arrest, release) are not offered. The engine still decides:
    these lists only save the player from typing ids.
    """
    people, ground, carried = view["people"], view["ground"], view["carried"]
    # Each entry: action, label, target choices, item choices, whether it needs a message.
    rows = [
        ("move", "Go to", view["exits"], None, False, True),
        ("look", "Look around", None, None, False, False),
        ("talk", "Talk to", people, None, True, True),
        ("take", "Take", None, ground, False, False),
        ("drop", "Drop", None, carried, False, False),
        ("give", "Give", people, carried, False, True),
        ("show", "Show", people, carried, False, False),
    ]
    empty_reasons = {
        "move": "nowhere to go", "talk": "nobody here to talk to",
        "take": "nothing to take here", "drop": "you carry nothing",
        "give": "nobody here to give to", "show": "nobody here to show",
    }
    out = []
    for action, label, targets, items, message, target_required in rows:
        reason = None
        if (targets == []) or (items == []):
            # nothing to pick from, so the action cannot be tried
            # Keep it visible so the player knows why.
            reason = ("you carry nothing" if items == [] and action != "take"
                      else empty_reasons[action])
        out.append({"action": action, "label": label, "targets": targets, "items": items,
                    "message": message, "target_required": target_required,
                    "reason": reason, "icon": ACTION_ICONS[action]})  # fmt: skip
    return out


def finish_view(world: World, sc: Scenario) -> tuple[str, str | None]:
    """The outcome (world facts) and the scenario secret, for the end of the game only."""
    names = story.names_from(sc)
    text = outcome.format_outcome(world.log.all(), names)
    murderer = sc.secrets.get("murderer")
    secret = f"murderer = {story.show(names, murderer)}" if murderer else None
    return text, secret
