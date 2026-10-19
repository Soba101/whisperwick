"""Using goods changes physical presence only. No model or network is needed."""

import json

import pytest
from helpers import SCENARIO, SEEDS, fresh_world, run_ticks

from whisperwick import llm_agent
from whisperwick.act_prompt import build_messages
from whisperwick.llm_client import FakeClient
from whisperwick.llm_intent import intent_schema
from whisperwick.memory import Memories
from whisperwick.player_commands import parse_command
from whisperwick.player_terminal import player_lines
from whisperwick.scenario import build_world, load_scenario
from whisperwick.story import format_event
from whisperwick.world import World

GOODS = SCENARIO.with_name("murder_of_the_mayor_goods.yaml")


@pytest.fixture
def world():
    return build_world(load_scenario(GOODS))


def use(world, actor="npc_alice", item="item_tea", **kw):
    return world.act(dict(actor=actor, action="use", item=item, **kw))


@pytest.mark.parametrize("actor,item,reason", [
    ("npc_alice", None, "unknown item None"),
    ("npc_alice", "missing", "unknown item missing"),
    ("player", "item_tea", "you are not holding that"),
    ("npc_sarah", "item_candle", "you are not holding that"),
    ("npc_alice", "item_mug", "that cannot be used up"),
    ("npc_victor", "item_boots", "that cannot be used up"),
])
def test_use_refusals_change_nothing(world, actor, item, reason):
    before = world.state_hash()
    result = use(world, actor, item)
    assert not result.ok and result.reason == reason
    assert world.state_hash() == before


def test_use_removes_item_and_logs_only_physical_fact(world):
    world.move("player", "loc_inn")
    world.move("npc_sarah", "loc_inn")
    world.npcs["npc_mayor"].location = "loc_inn"
    before = world.to_dict()
    result = use(world)
    assert result.ok
    item = world.items["item_tea"]
    assert item.holder is item.location is None
    assert "item_tea" not in world.items_at("loc_inn")
    assert "item_tea" not in world.items_held("npc_alice")
    event = result.event
    assert event == world.log.all()[-1]
    assert event.type == "use" and event.actor == "npc_alice"
    assert event.location == "loc_inn" and event.witnesses == ["npc_sarah", "player"]
    assert event.data == {"item": "item_tea", "item_name": "cup of tea",
                          "item_description": "a cup filled with tea", "use_verb": "drinks"}
    after = world.to_dict()
    assert before['npcs'] == after['npcs']
    assert before['rng'] == after['rng'] and before['tick'] == after['tick']
    assert [i for i in before['items'] if i['id'] != item.id] == [
        i for i in after['items'] if i['id'] != item.id]
    memories = Memories()
    memories.observe(event, world)
    assert set(memories) == {"npc_alice", "npc_sarah"}
    assert "Alice (npc_alice) used the cup of tea" in memories["npc_sarah"].memories[0].text
    assert "Alice drinks the cup of tea" in player_lines(world, [event])[0]
    assert use(world).reason == "you are not holding that"
    assert not world.act(dict(actor="npc_alice", action="take", item=item.id)).ok
    loaded = World.from_dict(json.loads(json.dumps(world.to_dict())))
    assert loaded.state_hash() == world.state_hash()


def test_scenarios_offer_only_explicit_consumables(world):
    verbs = {"item_coffee": "drinks", "item_tea": "drinks", "item_bread": "eats",
             "item_stew": "eats", "item_ale": "drinks", "item_apples": "eats"}
    assert {i.id: i.use_verb for i in world.items.values() if i.consumable} == verbs
    assert world.items["item_tea"].holder == "npc_alice"
    assert world.npcs["npc_alice"].location == "loc_inn"
    assert not any(i.consumable or i.use_verb for i in fresh_world().items.values())


def test_story_verb_is_scenario_data_and_defaults_to_uses(world):
    world.move("player", "loc_inn")
    world.act(dict(actor="npc_alice", action="give", item="item_tea", target="player"))
    world.clock.tick = 8 * 60 + 25
    event = use(world, "player", message="eats").event
    names = {"player": "Wren", "loc_inn": "The Inn"}
    assert format_event(event, names) == "08:25  The Inn: Wren drinks the cup of tea"
    # A name or a model message cannot choose the verb.
    world.items["item_coffee"].use_verb = None
    event = use(world, item="item_coffee", message="drinks").event
    assert "use_verb" not in event.data
    assert "uses the cup of coffee" in format_event(event, names)
    assert "eats the loaf of bread" in format_event(use(world, item="item_bread").event, names)


def test_model_and_terminal_can_propose_use(world):
    assert "use" in intent_schema(world, "npc_alice")["properties"]["action"]["enum"]
    reply = dict(action="use", item="item_tea", target=None, message=None)
    result = llm_agent.act(world, "npc_alice", FakeClient([reply]))
    assert result.ok and result.event.type == "use"
    assert "item_tea" not in intent_schema(world, "npc_alice")["properties"]["item"]["enum"]
    assert "item_tea" not in build_messages(world, "npc_alice")[0]["content"]
    kind, intent = parse_command("use item_tea")
    assert kind == "act" and intent.action == "use" and intent.item == "item_tea"
    assert parse_command("use") is None


@pytest.mark.parametrize("seed", SEEDS)
def test_use_then_stub_is_deterministic(world, seed):
    def run():
        w = build_world(load_scenario(GOODS), seed=seed)
        assert use(w).ok
        hashes = run_ticks(w, 120)
        return hashes, [e.model_dump() for e in w.log.all()]
    assert run() == run()


@pytest.mark.parametrize("field,value", [("use_verb", "drinks"), ("consumable", True)])
def test_model_cannot_override_item_rules_or_story_verb(world, field, value):
    before = world.state_hash()
    result = use(world, **{field: value})
    assert not result.ok and "malformed intent" in result.reason
    assert world.state_hash() == before


def test_scenario_cannot_start_with_an_absent_consumable():
    scenario = load_scenario(GOODS)
    tea = next(i for i in scenario.items if i.id == "item_tea")
    tea.holder = None
    with pytest.raises(ValueError, match="exactly one"):
        build_world(scenario)
