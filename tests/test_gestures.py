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
    "", " ", "a" * 81, "Bob nods\nBob smiles",
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
    "Bob glances at item_boots", "Bob glances at muddy boots", "Bob eyes the boots",
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
    assert "gesture (text" in text and "make (name" in text
