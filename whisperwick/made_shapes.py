"""The complete vocabulary for villager-made actions. No free code is accepted."""

import re

PARAMS = ("item", "person", "exit")
NEEDS = ("holds_item", "item_here", "item_hidden_here", "person_here")
EFFECTS = ("put_item_here", "hide_item_here", "reveal_hidden_here",
           "take_item_here", "move_self_exit")
# reveal_hidden_here searches all hidden ground items at the actor's current place.
REQUIRES = {"holds_item": "item", "item_here": "item", "item_hidden_here": "item",
            "person_here": "person", "put_item_here": "item", "hide_item_here": "item",
            "take_item_here": "item", "move_self_exit": "exit"}


def shape_problem(world, definition, *, new=False):
    """Check definitions on creation AND use, including records loaded from events."""
    from whisperwick.actions import HANDLERS

    if set(definition) != {"name", "params", "needs", "does"}:
        return "make needs name, params, needs and does"
    name = definition["name"]
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", name):
        return "action name must be 1-40 lowercase letters, digits or underscores"
    if name in {*HANDLERS, "recall", "wait"}:
        return "action name clashes with a built-in action"
    if new and any(name in actions for actions in world.made_actions.values()):
        return "action name already exists"
    for key in ("params", "needs", "does"):
        values = definition[key]
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            return f"{key} must be a list of strings"
        if len(values) > 12 or (key != "does" and len(values) != len(set(values))):
            return f"{key} has too many or repeated pieces"
    if not definition["does"]:
        return "does must contain an effect"
    if set(definition["params"]) - set(PARAMS):
        return "unknown parameter"
    for need in definition["needs"]:
        if need.startswith("at_place:"):
            if need.removeprefix("at_place:") not in world.locations:
                return "at_place names an unknown location"
        elif need not in NEEDS:
            return f"unknown need {need}"
    for effect in definition["does"]:
        if effect not in EFFECTS:
            return f"unknown effect {effect}"
    for piece in [*definition["needs"], *definition["does"]]:
        param = REQUIRES.get(piece)
        if param and param not in definition["params"]:
            return f"{piece} requires parameter {param}"
    return None


def argument_problem(world, actor, definition, args):
    if set(args) != set(definition["params"]):
        return "use arguments must match the declared params"
    here = world.npcs[actor].location
    if "item" in args and args["item"] not in world.items:
        return "unknown item"
    if "person" in args:
        person = world.npcs.get(args["person"])
        if person is None or not person.alive or person.location != here:
            return "person is not here"
    if "exit" in args and args["exit"] not in world.locations[here].links:
        return "exit is not reachable from here"
    return None
