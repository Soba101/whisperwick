"""LLM agent tests. A FakeClient stands in for the model: no network, ever."""

from helpers import fresh_world

from whisperwick import llm_agent
from whisperwick.actions import MAX_MESSAGE_CHARS
from whisperwick.llm_client import FakeClient, chat_url
from whisperwick.memory import MemoryStream


def schema_targets(schema):
    return set(schema["properties"]["target"]["enum"])


def test_schema_targets_are_exits_plus_people_here():
    world = fresh_world()
    # Bob is at the market with Victor. Exits from the market: inn, town hall, temple.
    schema = llm_agent.intent_schema(world, "npc_bob")
    assert schema_targets(schema) == {
        "loc_inn", "loc_town_hall", "loc_temple", "npc_victor", None,
    }  # fmt: skip
    assert schema["properties"]["action"]["enum"] == ["move", "talk", "look"]
    assert schema["properties"]["message"]["maxLength"] == MAX_MESSAGE_CHARS
    assert schema["required"] == ["action", "target", "message"]
    assert schema["additionalProperties"] is False
    assert "actor" not in schema["properties"]


def test_prompt_lists_ids_and_names():
    world = fresh_world()
    messages = llm_agent.build_messages(world, "npc_bob", memories=["I saw smoke."])
    text = messages[0]["content"]
    for needle in ["npc_bob", "blacksmith", "loc_market", "loc_inn", "npc_victor", "merchant",
                   "day 1 08:00", "I saw smoke."]:  # fmt: skip
        assert needle in text
    assert "rejected" not in text


def test_prompt_includes_feedback():
    world = fresh_world()
    text = llm_agent.build_messages(world, "npc_bob", feedback="npc_x is not here")[0]["content"]
    assert "Your last action was rejected: npc_x is not here. Choose again." in text


def test_valid_reply_moves_the_npc():
    world = fresh_world()
    client = FakeClient([{"action": "move", "target": "loc_inn", "message": None}])
    result = llm_agent.act(world, "npc_bob", client)
    assert result.ok
    assert world.npcs["npc_bob"].location == "loc_inn"
    assert len(client.calls) == 1


def test_name_instead_of_id_is_retried_with_reason_then_falls_back_to_look():
    world = fresh_world()
    bad = {"action": "talk", "target": "Victor", "message": "hi"}
    client = FakeClient([bad, bad])
    stats = {"calls": 0, "rejected": 0}
    result = llm_agent.act(world, "npc_bob", client, stats=stats)
    assert result.ok and result.observation is not None  # fell back to look
    assert len(client.calls) == 2
    # The second prompt carries the engine's reason.
    assert "rejected: unknown npc Victor" in client.calls[1]["messages"][0]["content"]
    assert stats == {"calls": 2, "rejected": 2}
    assert world.log.all() == []  # nothing happened in the world


def test_retry_can_succeed():
    world = fresh_world()
    bad = {"action": "talk", "target": "Victor", "message": "hi"}
    good = {"action": "talk", "target": "npc_victor", "message": "hi"}
    result = llm_agent.act(world, "npc_bob", FakeClient([bad, good]))
    assert result.ok and result.event.type == "talk"


def test_garbage_reply_becomes_look():
    world = fresh_world()
    intent = llm_agent.decide(world, "npc_bob", FakeClient([{"nonsense": 1}]))
    assert (intent.actor, intent.action) == ("npc_bob", "look")


def test_client_error_becomes_look():
    world = fresh_world()
    intent = llm_agent.decide(world, "npc_bob", FakeClient([]))  # nothing queued: raises
    assert intent.action == "look"


def test_chat_url_strips_v1():
    assert chat_url("http://h:11434/v1") == "http://h:11434/api/chat"
    assert chat_url("http://h:11434/v1/") == "http://h:11434/api/chat"
    assert chat_url("http://h:11434") == "http://h:11434/api/chat"


def test_errors_are_counted_and_last_error_kept():
    world = fresh_world()
    stats = {}
    llm_agent.decide(world, "npc_bob", FakeClient([]), stats=stats)  # model error
    llm_agent.decide(world, "npc_bob", FakeClient([{"nonsense": 1}]), stats=stats)  # bad reply
    assert stats["errors"] == 2
    assert stats["last_error"]  # some readable text


def test_act_passes_stats_to_decide():
    world = fresh_world()
    stats = {}
    result = llm_agent.act(world, "npc_bob", FakeClient([]), stats=stats)
    assert result.ok and result.observation is not None  # look
    assert stats["errors"] == 1  # the look fallback succeeded, so there was no second try


def test_good_reply_counts_no_errors():
    world = fresh_world()
    stats = {}
    client = FakeClient([{"action": "look", "target": None, "message": None}])
    llm_agent.decide(world, "npc_bob", client, stats=stats)
    assert "errors" not in stats


def test_memory_lines_use_people_and_place_as_query():
    world = fresh_world()
    stream = MemoryStream()
    stream.add(0, "Victor owes me coins", 5)
    stream.add(0, "the weather was mild", 5)
    assert llm_agent.memory_lines(stream, 0, world, "npc_bob", k=1) == ["Victor owes me coins"]


def test_prompt_shows_bodies_here():
    # Hal starts in the Town Hall with the mayor's body. The prompt must say so.
    world = fresh_world()
    text = llm_agent.build_messages(world, "npc_hal")[0]["content"]
    assert "Lying dead here: npc_mayor" in text
