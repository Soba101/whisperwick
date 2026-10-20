"""Gestures are bounded witnessed events. They cannot claim new physical facts."""

import pytest
from helpers import SCENARIO, fresh_world

from whisperwick.act_prompt import build_messages
from whisperwick.llm_agent import act
from whisperwick.llm_client import FakeClient
from whisperwick.memory import Memories
from whisperwick.player_terminal import player_lines
from whisperwick.player_web import WebPlayer
from whisperwick.scenario import load_scenario
from whisperwick.story import format_event


@pytest.mark.parametrize("text", [
    "Bob paces by the window", "wipes his hands", "Bob nods at Victor", "npc_bob paces"])
def test_gesture_is_seen_remembered_and_changes_only_the_log(text):
    w, memories = fresh_world(), Memories()
    before = w.to_dict()
    result = act(w, "npc_bob", FakeClient([{"action": "gesture", "text": text}]))
    assert result.ok and result.event.type == "gesture"
    assert result.event.witnesses == ["npc_victor", "player"]
    after = w.to_dict()
    after["events"] = before["events"]
    assert after == before
    memories.observe(result.event, w)
    words = text.removeprefix("Bob ").removeprefix("npc_bob ")
    assert words in memories["npc_victor"].memories[-1].text
    assert "npc_alice" not in memories
    assert "Bob" in format_event(result.event, {"npc_bob": "Bob"})
    assert words in player_lines(w, [result.event])[0]
    assert result.event.data["text"] == text
    player = WebPlayer(load_scenario(SCENARIO))
    player._refresh(w)
    assert player.interactions["npc_bob"]["sequence"] > 0


@pytest.mark.parametrize("text", [
    "", " ", "a" * 121, "Bob nods\nBob smiles",
    "Bob takes a stone", "Bob took a stone", "Bob is taking a stone",
    "Bob gives a stone", "Bob gave a stone", "Bob is giving a stone",
    "Bob opens the door", "Bob opened the door", "Bob is opening the door",
    "Bob closes the door", "Bob closed the door", "Bob is closing the door",
    "Bob hits Victor", "Bob punches Victor", "Bob is hitting Victor",
    "Bob hides a stone", "Bob hid a stone", "Bob is hiding a stone",
    "Bob moves Victor", "Bob moved a stone", "Bob is moving a stone",
    "Bob pushes Victor", "Bob drags Victor", "Bob carries a stone",
    "Bob hands Victor a stone", "Bob walks to the market", "Bob kills Victor",
    "Bob removes a stone", "Bob passes a stone",
    "Bob drops a stone", "Bob puts a stone down", "Bob picks a stone up",
    # Victor's boots are in view at the market, so only the raw id is refused (2026-10-21).
    "Bob glances at item_boots",
    "Bob nods at Alice", "Bob nods at npc_alice", "Bob nods at the mayor",
])
def test_bad_gesture_is_a_normal_atomic_rejection(text):
    w = fresh_world()
    before = w.state_hash()
    result = w.act({"actor": "npc_bob", "action": "gesture", "text": text})
    assert not result.ok and result.reason
    assert w.state_hash() == before


def test_player_cannot_gesture_and_prompt_has_only_plain_descriptions():
    w = fresh_world()
    assert not w.act({"actor": "player", "action": "gesture", "text": "nods"}).ok
    text = build_messages(w, "npc_bob")[0]["content"]
    assert "gesture (message" in text and "make (name" in text


# 2026-10-21 live runs: models wrote gestures into `message` and often wrote speech.
def test_gesture_in_message_field_is_accepted():
    w = fresh_world()
    words = "crosses arms and stares at the ground"
    result = w.act({"actor": "npc_bob", "action": "gesture", "message": words})
    assert result.ok and result.event.data["text"] == words


@pytest.mark.parametrize("words", [
    "Hm. New face. What do you want, stranger?", "I am not done yet.",
    'mutters "go away"', "You there.",
])
def test_speech_is_not_a_gesture(words):
    result = fresh_world().act({"actor": "npc_bob", "action": "gesture", "message": words})
    assert not result.ok and "use talk" in result.reason


def test_wiping_hands_is_not_handing_something_over():
    w = fresh_world()
    wipe = {"actor": "npc_bob", "action": "gesture", "message": "wipes soot off his hands"}
    assert w.act(wipe).ok
    assert not w.act({"actor": "npc_bob", "action": "gesture", "message": "hands over a coin"}).ok


def test_pointing_at_an_item_in_view_is_a_gesture():
    w = fresh_world()
    here = w.npcs["npc_bob"].location
    seen = w.items_at(here, "npc_bob") + [i for n in w.npcs_at(here) for i in w.items_held(n)]
    gone = [i for i in w.items if i not in seen]
    if seen:
        name = w.items[seen[0]].name
        point = {"actor": "npc_bob", "action": "gesture", "message": f"points at the {name}"}
        assert w.act(point).ok
    if gone:
        name = w.items[gone[0]].name
        assert not w.act({"actor": "npc_bob", "action": "gesture",
                          "message": f"points at the {name}"}).ok
    wave = {"actor": "npc_bob", "action": "gesture", "message": "waves hand dismissively"}
    assert w.act(wave).ok


@pytest.mark.parametrize("words", [
    "Whoa, careful with that basket. Those apples look ripe and heavy!",
    "Don't let them go rolling into my good shoes.", "Hey, over here.",
])
def test_exclamations_and_orders_are_speech(words):
    result = fresh_world().act({"actor": "npc_bob", "action": "gesture", "message": words})
    assert not result.ok and "use talk" in result.reason


def test_gesture_lines_carry_the_place_like_other_lines():
    w = fresh_world()
    event = w.act({"actor": "npc_bob", "action": "gesture", "message": "waves cheerfully"}).event
    from whisperwick import story
    line = format_event(event, story.names_from(load_scenario(SCENARIO)))
    assert "Bob waves cheerfully" in line and w.locations[event.location].name + ":" in line
