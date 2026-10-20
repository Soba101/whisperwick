"""Made actions replay through the engine, and survive save/load and seeded runs."""

import json

import pytest
from helpers import SCENARIO, fresh_world
from made_helpers import HIDE, REVEAL, make

from whisperwick.llm_agent import act
from whisperwick.llm_client import FakeClient
from whisperwick.llm_intent import intent_schema
from whisperwick.replay_state import state_at
from whisperwick.scenario import load_scenario
from whisperwick.screen_source import intent_reply
from whisperwick.stub_agent import intents_for_tick
from whisperwick.world import World


def test_save_load_rebuilds_registry_and_hidden_fields():
    w = fresh_world()
    assert make(w, use={"item": "item_boots"}).ok
    saved = json.loads(json.dumps(w.to_dict()))
    assert "made_actions" not in saved  # there is only one source of definitions
    loaded = World.from_dict(saved)
    assert loaded.made_actions == w.made_actions
    assert loaded.state_hash() == w.state_hash()
    assert loaded.items["item_boots"].hidden
    assert loaded.items["item_boots"].known_by == ["npc_victor"]
    for world in (w, loaded):
        assert make(world, REVEAL, use={}).ok
    assert loaded.state_hash() == w.state_hash()


def test_event_proposals_replay_identically_and_only_maker_sees_own_actions():
    w, replay = fresh_world(), fresh_world()
    assert make(w, use={"item": "item_boots"}).ok
    assert make(w, REVEAL, use={}).ok
    assert w.act({"actor": "npc_victor", "action": "uncover"}).ok
    for event in w.log.all():
        result = act(replay, event.actor, FakeClient([intent_reply(event)]))
        assert result.ok
    assert replay.state_hash() == w.state_hash()
    assert replay.made_actions == w.made_actions
    state = state_at(load_scenario(SCENARIO), w.log.all(), w.clock.tick)
    assert state["made_actions"] == w.made_actions
    assert state["items"] == {i: item.model_dump() for i, item in w.items.items()}
    own = intent_schema(w, "npc_victor")["properties"]["action"]["enum"]
    others = intent_schema(w, "npc_bob")["properties"]["action"]["enum"]
    assert "tuck_away" in own and "uncover" in own
    assert "tuck_away" not in others and "uncover" not in others


@pytest.mark.parametrize("seed", [1, 42, 1234])
def test_seeded_stub_with_new_actions_is_deterministic_across_resume(seed):
    def run(resume=False):
        w, hashes = fresh_world(seed), []
        assert make(w, HIDE, use={"item": "item_boots"}).ok
        assert make(w, REVEAL, actor="npc_bob").ok
        for tick in range(300):
            proposals = intents_for_tick(w)
            if tick % 17 == 0:
                proposals.append({"actor": "npc_bob", "action": "uncover"})
            if tick % 11 == 0:
                proposals.append({"actor": "npc_victor", "action": "gesture", "text": "nods"})
            w.step(proposals)
            hashes.append(w.state_hash())
            if resume and tick == 149:
                old = w
                w = World.from_dict(json.loads(json.dumps(w.to_dict())))
                old.log.db.close()
        return hashes
    assert run() == run() == run(resume=True)


def test_replay_page_tracks_made_moves_and_gesture_text():
    from whisperwick.replay_data import build_data

    w = fresh_world()
    definition = {"action": "make", "name": "walk_on", "params": ["exit"],
                  "needs": [], "does": ["move_self_exit"]}
    assert make(w, definition, use={"exit": "loc_inn"}).ok
    assert w.act({"actor": "npc_victor", "action": "gesture", "text": "nods"}).ok
    data = build_data(load_scenario(SCENARIO), w.log.all())
    assert data["events"][0]["moves"] == ["loc_inn"]
    assert data["events"][1]["text"] == "Victor nods"
    assert state_at(load_scenario(SCENARIO), w.log.all(), w.clock.tick)[
        "positions"]["npc_victor"] == "loc_inn"


def test_new_schema_has_no_empty_enums_and_own_params_are_plain():
    from whisperwick.act_prompt import build_messages

    w = fresh_world()
    for actor in ("npc_alice", "npc_bob", "npc_hal"):
        assert '"enum": []' not in json.dumps(intent_schema(w, actor))
    assert make(w).ok
    assert "Your action: tuck_away (params: item;" in build_messages(
        w, "npc_victor")[0]["content"]
    assert "Your action: tuck_away" not in build_messages(w, "npc_bob")[0]["content"]
