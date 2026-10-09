"""Memory tests. A FakeClient stands in for the model: no network, ever."""

from helpers import fresh_world

from whisperwick import memory
from whisperwick.clock import Clock
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


def test_seed_evidence_adds_important_evidence_in_sorted_npc_order():
    memories = Memories()
    evidence = {"npc_bob": ["saw Victor"], "npc_alice": ["mud on his boots", "a strong drink"]}
    memory.seed_evidence(memories, evidence, tick=480)
    assert list(memories) == ["npc_alice", "npc_bob"]  # made in sorted order
    first = memories["npc_alice"].memories[0]
    assert (first.tick, first.importance, first.kind) == (480, 9, "evidence")
    assert [m.text for m in memories["npc_alice"].memories] == evidence["npc_alice"]


def test_observe_stores_the_event_id_and_look_and_evidence_have_none():
    w, mem = fresh_world(), Memories()
    r = w.act({"actor": "npc_bob", "action": "talk", "target": "npc_victor", "message": "hi"})
    mem.observe(r.event, w)
    # Bob (actor) and Victor (listener) both remember it, with the event's id.
    assert mem["npc_bob"].memories[0].event_id == r.event.id is not None
    assert mem["npc_victor"].memories[0].event_id == r.event.id
    mem.observe_look("npc_bob", {"location": "loc_market", "people": [], "exits": []}, 5)
    memory.seed_evidence(mem, {"npc_bob": ["saw Victor"]}, 0)
    assert [m.event_id for m in mem["npc_bob"].memories[1:]] == [None, None]


def test_memory_id_is_the_index_and_stays_stable_as_the_stream_grows():
    stream = MemoryStream()
    stream.add(0, "first", 1)
    assert memory.memory_id(0) == "m0"
    stream.add(1, "second", 1)
    assert stream.memories[0].text == "first" and memory.memory_id(1) == "m1"
