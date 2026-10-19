"""Scene words must have a visible source. No model or network is needed."""

import pytest
from helpers import fresh_world

from whisperwick.actions import Intent, do_look
from whisperwick.crime import generate
from whisperwick.events import Event
from whisperwick.narrator import scene, time_of_day
from whisperwick.scenario import build_world


def look(world):
    return do_look(world, Intent(actor="player", action="look")).observation


@pytest.mark.parametrize("hour,word", [
    (0, "night"), (5, "night"), (6, "morning"), (11, "morning"),
    (12, "midday"), (13, "midday"), (14, "afternoon"), (17, "afternoon"),
    (18, "evening"), (21, "evening"), (22, "night"), (23, "night"),
])
def test_time_words_repeat_each_day(hour, word):
    assert time_of_day(hour * 60) == time_of_day(1440 + hour * 60) == word


def test_same_input_same_words_and_no_engine_effects():
    world = fresh_world()
    seen = look(world)
    before = world.state_hash()
    text = scene(world, seen, 42)
    assert all(scene(world, seen, 42) == text for _ in range(5))
    assert world.state_hash() == before  # Includes events and the engine RNG.
    restored = type(world).from_dict(world.to_dict())
    assert scene(restored, seen, 42) == text


def test_latest_witnessed_action_and_no_invented_work_or_hidden_details():
    world = fresh_world()
    world.act(Intent(actor="npc_bob", action="talk", target="player", message="A secret tale"))
    # Later unseen and future events cannot change what Wren last saw Bob do.
    for tick, witnesses in [(world.clock.tick, []), (world.clock.tick + 1, ["player"])]:
        world.log.append(Event(tick=tick, type="use", actor="npc_bob", location="loc_market",
                               data={"item_name": "hidden treasure"}, witnesses=witnesses))
    text = scene(world, look(world), 42)
    assert "speaking" in text
    assert all(word not in text for word in ["treasure", "secret tale", "Alice", "wipes", "boots"])
    # An unsupported latest event falls back to presence, rather than an older action.
    world.log.append(Event(tick=world.clock.tick, type="unknown", actor="npc_bob",
                           location="loc_market", witnesses=["player"]))
    assert "speaking" not in scene(world, look(world), 42)


@pytest.mark.parametrize("action,phrase", [
    ("move", "arriving here"), ("talk", "speaking"), ("take", "picking something up"),
    ("drop", "putting something down"), ("give", "handing something over"),
    ("show", "showing an item"), ("use", "using an item"),
    ("arrest", "making an arrest"), ("release", "releasing someone from custody"),
])
def test_action_words_require_a_matching_witnessed_event(action, phrase):
    world = fresh_world()
    event = Event(tick=world.clock.tick, type=action, actor="npc_bob", location="loc_market")
    world.log.append(event)
    assert phrase not in scene(world, look(world), 42)
    world.log.append(event.model_copy(update={"witnesses": ["player"]}))
    assert phrase in scene(world, look(world), 42)
    # Seeing an action somewhere else does not imply it happened here.
    world.log.append(event.model_copy(update={"witnesses": ["player"], "location": "loc_inn"}))
    assert phrase not in scene(world, look(world), 42)


@pytest.mark.parametrize("seed", range(12))
def test_generated_crime_sentences_all_map_to_look_facts(seed):
    world = build_world(generate(seed))
    # Check every place, including the body and any privately carried evidence.
    for place in world.locations:
        world.npcs["player"].location = place
        seen = look(world)
        text = scene(world, seen, seed)
        allowed = {
            f"Morning at {world.locations[place].name}",
            f"It is morning at {world.locations[place].name}",
        }
        for person in seen["people"]:
            who = world.npcs[person].name
            allowed.update([f"{who} is here", f"You see {who} here"])
            assert who in text
        for body in seen["bodies"]:
            who = world.npcs[body].name
            allowed.update([f"{who}'s body lies here", f"You see the body of {who} here"])
            assert who in text
        for key, table, templates in [
            ("items", world.items, ("On the ground: {}", "You see {} on the ground")),
            ("exits", world.locations, ("Open ways lead to {}", "The ways to {} are open")),
        ]:
            labels = ", ".join(table[i].name for i in sorted(seen[key]))
            if labels:
                allowed.update(t.format(labels) for t in templates)
                assert labels in text
        # This checks whole sentences, rather than merely finding expected names.
        assert set(text.rstrip(".").split(". ")) <= allowed
        hidden_items = [i.name for i in world.items.values()
                        if i.id not in seen["items"]]
        visible_names = {world.items[i].name for i in seen["items"]}
        # A visible coil of rope may share words with a hidden crime weapon.
        assert all(name not in text for name in hidden_items
                   if not any(name in visible for visible in visible_names))


def test_observation_limits_presence_custody_and_empty_exits():
    world = fresh_world()
    seen = look(world)
    seen.update(people=["npc_bob"], held=["npc_bob"], items=[], bodies=[], exits=[])
    text = scene(world, seen, 42)
    assert "Bob" in text and "custody" in text
    assert "Victor" not in text and "ground" not in text
    assert "no ways out" in text or "No way leads out" in text
