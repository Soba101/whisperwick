"""Memory tests. A FakeClient stands in for the model: no network, ever."""

from helpers import fresh_world

from whisperwick import memory
from whisperwick.clock import Clock
from whisperwick.llm_client import FakeClient
from whisperwick.memory import Memories, MemoryStream


def test_retrieve_prefers_important_memories():
    stream = MemoryStream()
    stream.add(10, "bread was cheap", 2)
    stream.add(10, "a body was found", 9)
    assert [m.text for m in stream.retrieve(10, "", k=1)] == ["a body was found"]


def test_recency_decays_with_game_minutes():
    stream = MemoryStream()
    stream.add(0, "old news", 5)
    stream.add(900, "fresh news", 5)
    # Same importance and relevance, so only age decides.
    assert [m.text for m in stream.retrieve(1000, "", k=1)] == ["fresh news"]


def test_relevance_counts_shared_words():
    stream = MemoryStream()
    stream.add(100, "Victor sold a knife at the market", 5)
    stream.add(100, "the weather was mild", 5)
    top = stream.retrieve(100, "victor knife", k=1)
    assert top[0].text.startswith("Victor sold")


def test_short_words_and_ids_are_handled():
    stream = MemoryStream()
    stream.add(1, "saw npc_victor at loc_inn", 5)
    stream.add(1, "an ox is in it", 5)  # only short words: no overlap
    assert stream.retrieve(1, "Victor", k=1)[0].text.startswith("saw npc_victor")


def test_results_are_chronological_and_ties_are_deterministic():
    stream = MemoryStream()
    for tick in (5, 3, 4):
        stream.add(tick, f"same score {tick}", 5)
    # Importance is equal, so the newest two win, then they read oldest first.
    first = stream.retrieve(5, "", k=2)
    assert [m.tick for m in first] == sorted(m.tick for m in first)
    assert [m.tick for m in first] == [4, 5]
    assert first == stream.retrieve(5, "", k=2)


def test_equal_ticks_are_stable():
    stream = MemoryStream()
    stream.add(7, "first", 5)
    stream.add(7, "second", 5)
    assert [m.text for m in stream.retrieve(7, "", k=1)] == ["second"]
    assert [m.text for m in stream.retrieve(7, "", k=5)] == ["first", "second"]


def test_describe_lines():
    world = fresh_world()
    world.act({"actor": "npc_bob", "action": "talk", "target": "npc_victor", "message": "Morning"})
    world.move("npc_victor", "loc_inn")  # then Victor walks away
    talk, move = world.log.all()
    assert memory.describe(talk, world, "npc_victor") == (
        'Day 1 08:00 at loc_market: Bob (npc_bob) said to you: "Morning"'
    )
    assert "You said to Victor (npc_victor)" in memory.describe(talk, world, "npc_bob")
    assert "said to Victor (npc_victor)" in memory.describe(talk, world, "npc_x")
    assert "Victor (npc_victor) left for loc_inn" in memory.describe(move, world, "npc_bob")
    assert "You walked to loc_inn" in memory.describe(move, world, "npc_victor")


def test_importance_rules():
    world = fresh_world()
    world.act({"actor": "npc_bob", "action": "talk", "target": "npc_victor", "message": "hi"})
    world.move("npc_bob", "loc_inn")
    talk, move = world.log.all()
    assert memory.importance_of(talk, "npc_victor") == 6
    assert memory.importance_of(talk, "npc_other") == 4
    assert memory.importance_of(move, "npc_victor") == 2


def test_observe_goes_to_witnesses_and_actor_only():
    world = fresh_world()
    mem = Memories()
    intent = {"actor": "npc_bob", "action": "talk", "target": "npc_victor", "message": "hi"}
    result = world.act(intent)
    mem.observe(result.event, world)
    assert set(mem) == {"npc_bob", "npc_victor"}  # only the actor and the one witness
    assert "You said to Victor" in mem["npc_bob"].memories[0].text
    assert mem["npc_victor"].memories[0].importance == 6


def test_observe_look_stores_a_cheap_line():
    mem = Memories()
    obs = {"location": "loc_market", "people": ["npc_victor"], "exits": ["loc_inn"]}
    mem.observe_look("npc_bob", obs, Clock.at(1, 8).tick)
    only = mem["npc_bob"].memories[0]
    assert only.importance == 1
    assert "npc_victor" in only.text and "loc_market" in only.text


def test_reflect_stores_a_reflection():
    stream = MemoryStream()
    stream.add(1, "Victor looked nervous", 4)
    client = FakeClient([{"thoughts": "Victor is hiding something."}])
    got = memory.reflect(stream, "Bob", client, tick=60)
    assert (got.kind, got.importance, got.tick) == ("reflection", 8, 60)
    assert stream.memories[-1] is got
    assert "Victor looked nervous" in client.calls[0]["messages"][0]["content"]
    assert client.calls[0]["schema"]["required"] == ["thoughts"]


def test_reflect_returns_none_on_failure():
    stream = MemoryStream()
    assert memory.reflect(stream, "Bob", FakeClient([]), tick=60) is None  # model error
    assert memory.reflect(stream, "Bob", FakeClient([{"oops": 1}]), tick=60) is None
    assert stream.memories == []
