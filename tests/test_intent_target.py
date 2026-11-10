"""The reply schema ties target to action (#129): no place id for talk, no person for move."""

from helpers import fresh_world

from whisperwick.llm_intent import exits_and_people, intent_schema


def allowed(schema: dict, action: str, target) -> bool:
    """Tiny checker for the anyOf rule: some branch must accept this action and target."""
    return any(
        action in b["properties"]["action"]["enum"] and target in b["properties"]["target"]["enum"]
        for b in schema["anyOf"]
    )


def setup(npc="npc_bob"):
    w = fresh_world()
    exits, people = exits_and_people(w, npc)
    return w, intent_schema(w, npc), exits, people


def test_person_action_rejects_a_place_id():
    _, schema, exits, people = setup("npc_bob")
    assert exits and people  # the test means nothing without both
    assert not allowed(schema, "talk", exits[0])
    assert allowed(schema, "talk", people[0])
    assert not allowed(schema, "talk", None)


def test_move_rejects_a_person_and_null():
    _, schema, exits, people = setup("npc_bob")
    assert allowed(schema, "move", exits[0])
    assert not allowed(schema, "move", people[0])
    assert not allowed(schema, "move", None)


def test_show_may_be_null_and_other_actions_only_null():
    _, schema, exits, people = setup("npc_bob")
    assert allowed(schema, "show", None) and allowed(schema, "show", people[0])
    assert not allowed(schema, "show", exits[0])
    assert allowed(schema, "look", None)
    assert not allowed(schema, "look", people[0])


def test_authority_may_arrest_any_living_person():
    w, schema, _, here = setup("npc_hal")
    far = [n for n, p in w.npcs.items() if p.alive and n != "npc_hal" and n not in here]
    assert far
    assert allowed(schema, "arrest", far[0])
    assert not allowed(schema, "arrest", "loc_inn")


def test_top_level_shape_is_unchanged():
    _, schema, _, _ = setup()
    assert list(schema["properties"])[:2] == ["action", "target"]
    assert schema["additionalProperties"] is False
