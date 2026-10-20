"""Hidden item identity and location stay out of other people's views and memories."""

import json

from helpers import SCENARIO, fresh_world
from made_helpers import HIDE, REVEAL, hidden_world, make

from whisperwick.act_prompt import build_messages
from whisperwick.exchange_prompt import build_messages as exchange_messages
from whisperwick.llm_intent import intent_schema
from whisperwick.memory import Memories
from whisperwick.narrator import scene
from whisperwick.player_terminal import player_lines, view_lines
from whisperwick.player_web import WebPlayer
from whisperwick.scenario import load_scenario
from whisperwick.web_state import you_view


def test_hidden_items_stay_out_of_look_prompts_memories_narrator_and_pages():
    w, mem = hidden_world(), Memories()
    for actor in ("npc_bob", "player"):
        obs = w.act({"actor": actor, "action": "look"}).observation
        assert "item_boots" not in obs["items"]
        mem.observe_look(actor, obs, w.clock.tick, w)
        assert "boots" not in scene(w, obs, 1, observer=actor)
        assert "boots" not in build_messages(w, actor)[0]["content"]
        assert "item_boots" not in json.dumps(intent_schema(w, actor))
        assert not w.act({"actor": actor, "action": "take", "item": "item_boots"}).ok
    assert "boots" not in mem["npc_bob"].memories[0].text
    assert w.act({"actor": "npc_victor", "action": "look"}).observation["items"] == ["item_boots"]
    assert "item_boots" in build_messages(w, "npc_victor")[0]["content"]
    assert "boots" not in json.dumps(you_view(w))
    assert "boots" not in " ".join(view_lines(w))
    hide = w.log.all()[-1]
    mem.observe(hide, w)
    assert len(mem["npc_bob"].memories) == 1  # no new memory of the hiding
    assert "boots" in mem["npc_victor"].memories[-1].text
    assert not player_lines(w, [hide])
    player = WebPlayer(load_scenario(SCENARIO))
    player._refresh(w)
    assert "boots" not in json.dumps(player.snapshot())


def test_reveal_grants_knowledge_to_present_people_but_not_later_arrivals():
    w, mem = hidden_world(), Memories()
    result = make(w, REVEAL, actor="npc_bob", use={})
    assert result.ok
    mem.observe(result.event, w)
    for actor in ("npc_bob", "npc_victor", "player"):
        assert "item_boots" in w.act({"actor": actor, "action": "look"}).observation["items"]
    assert "boots" in mem["npc_bob"].memories[-1].text
    assert "boots" in player_lines(w, [result.event])[0]
    assert "boots" in json.dumps(you_view(w))
    assert w.move("npc_alice", "loc_market").ok
    assert not w.act({"actor": "npc_alice", "action": "look"}).observation["items"]
    assert "boots" not in build_messages(w, "npc_alice")[0]["content"]


def test_multi_step_audiences_do_not_leak_hidden_steps_to_shared_prompts():
    w = fresh_world()
    definition = {**HIDE, "name": "stash_and_go", "params": ["item", "exit"],
                  "does": ["hide_item_here", "move_self_exit"]}
    event = make(w, definition, use={"item": "item_boots", "exit": "loc_inn"}).event
    mem = Memories()
    mem.observe(event, w)
    assert "boots" not in mem["npc_bob"].memories[-1].text
    assert "boots" not in player_lines(w, [event])[0]
    assert "boots" not in exchange_messages(w, "npc_victor", "npc_bob", {})[0]["content"]


def test_rehiding_resets_old_knowledge():
    w = hidden_world()
    assert make(w, REVEAL, actor="npc_bob", use={}).ok
    assert w.act({"actor": "npc_victor", "action": "take", "item": "item_boots"}).ok
    assert w.act({"actor": "npc_victor", "action": "tuck_away", "item": "item_boots"}).ok
    assert w.items["item_boots"].known_by == ["npc_victor"]
    assert you_view(w)["ground"] == []
