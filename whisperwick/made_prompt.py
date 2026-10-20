"""Plain action descriptions and schema pieces. No advice about choosing actions."""

from whisperwick.gestures import MAX_GESTURE_CHARS
from whisperwick.made_shapes import EFFECTS, NEEDS, PARAMS

ACTION_TEXT = (
    " gesture (text = a gesture with no physical result, at most 80 characters)."
    " make (name, params = a subset of item/person/exit, needs, does;"
    " optional use = {item/person/exit ids})."
    " Needs: holds_item, item_here, item_hidden_here, person_here, at_place:<location id>."
    " Effects: put_item_here, hide_item_here, reveal_hidden_here (all hidden items here),"
    " take_item_here, move_self_exit."
)


def own_actions(world, actor):
    return [f"Your action: {name} (params: {', '.join(d['params']) or 'none'}; "
            f"needs: {', '.join(d['needs']) or 'none'}; does: {', '.join(d['does'])})."
            for name, d in sorted(world.made_actions.get(actor, {}).items())]


def properties(world, items, people, exits):
    """The engine still validates all fields even when a client ignores this schema."""
    # Empty enums can break constrained decoders. Unavailable arguments are omitted.
    args = {key: {"enum": ids} for key, ids in
            (("item", items), ("person", people), ("exit", exits)) if ids}
    return {
        "text": {"type": ["string", "null"], "maxLength": MAX_GESTURE_CHARS},
        "name": {"type": ["string", "null"], "pattern": "^[a-z][a-z0-9_]{0,39}$"},
        "params": {"type": ["array", "null"], "items": {"enum": list(PARAMS)}},
        "needs": {"type": ["array", "null"], "items": {"enum": [
            *NEEDS, *(f"at_place:{loc}" for loc in sorted(world.locations))]}},
        "does": {"type": ["array", "null"], "items": {"enum": list(EFFECTS)}},
        "use": {"type": ["object", "null"], "properties": args, "additionalProperties": False},
        "person": {"enum": [*people, None]},
        "exit": {"enum": [*exits, None]},
    }
