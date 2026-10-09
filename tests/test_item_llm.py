"""LLM side of items: schema, prompt, intents, memories, story, scheduler. Fake clients only."""

from helpers import SCENARIO, fresh_world

from whisperwick import llm_agent, llm_intent, memory
from whisperwick.clock import Clock
from whisperwick.events import Event
from whisperwick.llm_client import FakeClient
from whisperwick.memory import Memories
from whisperwick.scenario import load_scenario
from whisperwick.scheduler import COOLDOWN, Scheduler
from whisperwick.story import format_event, names_from

NAMES = names_from(load_scenario(SCENARIO))


def item_enum(world, npc):
    return set(llm_agent.intent_schema(world, npc)["properties"]["item"]["enum"])


def test_schema_item_enum_is_ground_plus_held_plus_null():
    w = fresh_world()
    assert item_enum(w, "npc_hal") == {"item_knife", None}  # knife lies in his room
    assert item_enum(w, "npc_victor") == {"item_boots", None}  # he holds the boots
    assert item_enum(w, "npc_bob") == {None}  # nothing here or held
    assert "item" in llm_agent.intent_schema(w, "npc_bob")["required"]
    for verb in ["take", "drop", "give", "show"]:
        assert verb in llm_intent.ACTIONS


def test_prompt_lists_items_here_and_carried():
    w = fresh_world()
    hal = llm_agent.build_messages(w, "npc_hal")[0]["content"]
    assert "item_knife (bloody knife: a kitchen knife" in hal
    assert "You carry: nothing" in hal
    victor = llm_agent.build_messages(w, "npc_victor")[0]["content"]
    assert "You carry: item_boots (muddy boots: " in victor
    assert "Items on the ground here: nothing" in victor
    assert "never invent objects" in victor.lower()


def test_llm_item_reply_becomes_a_working_intent():
    w = fresh_world()
    reply = {"action": "take", "target": None, "item": "item_knife", "message": None}
    result = llm_agent.act(w, "npc_hal", FakeClient([reply]))
    assert result.ok and result.event.type == "take"
    assert w.items["item_knife"].holder == "npc_hal"


def item_event(w, actor, verb, **kw):
    return w.act({"actor": actor, "action": verb, **kw}).event


def test_memory_text_and_importance_for_each_item_event():
    w = fresh_world()
    give = item_event(w, "npc_victor", "give", item="item_boots", target="npc_bob")
    show = item_event(w, "npc_bob", "show", item="item_boots", target="player")
    drop = item_event(w, "npc_bob", "drop", item="item_boots")
    take = item_event(w, "npc_bob", "take", item="item_boots")
    to_me = memory.describe(give, w, "npc_bob")
    assert "Victor (npc_victor) gave you the muddy boots (Victor's boots, caked" in to_me
    assert "gave Bob (npc_bob) the muddy boots (" in memory.describe(give, w, "player")
    assert "You showed Wren (player) the muddy boots (" in memory.describe(show, w, "npc_bob")
    assert "Bob (npc_bob) dropped the muddy boots" in memory.describe(drop, w, "player")
    assert "You picked up the muddy boots" in memory.describe(take, w, "npc_bob")
    assert memory.importance_of(give, "npc_bob") == 8  # I am the receiver
    assert memory.importance_of(give, "player") == 7  # I only saw it
    assert memory.importance_of(show, "player") == 8
    assert memory.importance_of(drop, "player") == 5
    assert memory.importance_of(take, "npc_bob") == 5


def test_show_to_everyone_is_worded_for_the_room():
    w = fresh_world()
    e = item_event(w, "npc_victor", "show", item="item_boots")
    assert "showed everyone here the muddy boots" in memory.describe(e, w, "npc_bob")


def test_observe_look_remembers_ground_items_by_name():
    w, mem = fresh_world(), Memories()
    obs = w.act({"actor": "npc_hal", "action": "look"}).observation
    mem.observe_look("npc_hal", obs, Clock.at(1, 8).tick, w)
    line = mem["npc_hal"].memories[0]
    assert "bloody knife (item_knife)" in line.text and line.importance >= 5


def test_story_lines_for_item_events():
    w = fresh_world()
    give = item_event(w, "npc_victor", "give", item="item_boots", target="npc_bob")
    assert "Victor gives the muddy boots to Bob" in format_event(give, NAMES)
    show = item_event(w, "npc_bob", "show", item="item_boots")
    assert "Bob shows the muddy boots to everyone" in format_event(show, NAMES)
    drop = item_event(w, "npc_bob", "drop", item="item_boots")
    assert "Bob drops the muddy boots" in format_event(drop, NAMES)
    take = item_event(w, "npc_bob", "take", item="item_boots")
    assert "Bob takes the muddy boots" in format_event(take, NAMES)


def test_scheduler_wakes_give_and_show_targets():
    for verb in ("give", "show"):
        s = Scheduler(["npc_a", "npc_b", "npc_c"])
        noon = Clock.at(1, 12).tick
        for n in ("npc_a", "npc_b", "npc_c"):
            s.acted(n, noon)
        data = {"item": "i", "item_name": "x", "item_description": "y", "to": "npc_b"}
        s.notice(Event(tick=noon, type=verb, actor="npc_a", location="loc_inn", data=data))
        assert s.due(noon + COOLDOWN) == ["npc_b"]  # no witnesses listed: only the target
