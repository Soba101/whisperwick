"""Recall: search ranking, recall while acting, recall while thinking. No network, ever."""

import json

import pytest
from helpers import fresh_world
from test_thinking import EVIDENCE, bob_stream, good

from whisperwick import llm_agent, settings, thinking
from whisperwick.agent_log import AgentLog
from whisperwick.belief_log import BeliefLog
from whisperwick.llm_client import FakeClient
from whisperwick.memory import MemoryStream
from whisperwick.notebook import Notebooks
from whisperwick.recall import Private, search


def stream():
    s = MemoryStream()
    s.add(1, "The knife lay by the well.", 3)  # m0
    s.add(2, "Bob sold a knife and a sword.", 3)  # m1
    s.add(3, "Nothing happened at the temple.", 1, "reflection")  # m2
    s.add(4, "A knife again, and a sword.", 3)  # m3
    return s


def private_for(s):
    return Private(s, Notebooks(), AgentLog())


def test_search_ranks_by_shared_words_ties_to_newer_oldest_first():
    # "knife sword": m1 and m3 share 2 words, m0 shares 1.
    got = search(stream(), "knife sword", rank=False)
    assert [i for i, _ in got] == ["m0", "m1", "m3"]
    assert [i for i, _ in search(stream(), "knife", rank=False)] == ["m0", "m1", "m3"]


def test_search_keeps_top_five_newer_wins_ties_and_empty_is_empty(monkeypatch):
    s = MemoryStream()
    for i in range(8):
        s.add(i, "the knife", 1)
    old = search(s, "knife", rank=False)
    assert [i for i, _ in old] == ["m3", "m4", "m5", "m6", "m7"]
    monkeypatch.delenv("WHISPERWICK_RECALL_RANK", raising=False)
    assert search(s, "knife") == old
    assert search(stream(), "knife") == search(stream(), "knife", rank=False)
    assert search(stream(), "zebra", rank=False) == []
    assert search(stream(), "", rank=False) == []
    # all kinds are searched, reflections too
    assert [i for i, _ in search(stream(), "temple", rank=False)] == ["m2"]


def test_rank_rare_words_beat_common_words():
    s = MemoryStream()
    s.add(0, "The door was forced.", 3)
    for i in range(8):
        s.add(i + 1, f"Victor Hal met at place {i}.", 1)
    query = "victor hal door forced"
    assert [i for i, _ in search(s, query, rank=False)] == ["m4", "m5", "m6", "m7", "m8"]
    assert [i for i, _ in search(s, query, rank=True)] == ["m0", "m5", "m6", "m7", "m8"]


def test_rank_near_copies_take_one_slot():
    s = MemoryStream()
    for i in range(4):
        s.add(i, f"A knife beside door {i}.", 1)
    for i in range(5):
        s.add(i, f"Day {i + 1} 11:48 at loc_{i}: Knife   reflection.", 3, "reflection")
    got = search(s, "knife", rank=True)
    assert [i for i, _ in got] == ["m0", "m1", "m2", "m3", "m8"]
    # A cited copy also keeps the newer copies from using another slot.
    assert [i for i, _ in search(s, "m4 knife", rank=True)] == ["m0", "m1", "m2", "m3", "m4"]


def test_rank_ids_reserve_slots_and_ignore_missing_ids():
    assert [i for i, _ in search(stream(), "m2 something m999", rank=True)] == ["m2"]
    assert search(stream(), "m999", rank=True) == []
    s = stream()
    for i in range(8):
        s.add(i, f"Something at place {i}.", 1)
    assert [i for i, _ in search(s, "M2 m2 m0 m1 m3 m4 something", rank=True)] == [
        "m0", "m1", "m2", "m3", "m4",
    ]


def test_recall_rank_setting(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    monkeypatch.delenv("WHISPERWICK_RECALL_RANK", raising=False)
    assert settings.recall_rank(env_path) is False
    env_path.write_text("WHISPERWICK_RECALL_RANK=on\n")
    assert settings.recall_rank(env_path) is True
    monkeypatch.setenv("WHISPERWICK_RECALL_RANK", "off")
    assert settings.recall_rank(env_path) is False
    monkeypatch.setenv("WHISPERWICK_RECALL_RANK", "bad")
    with pytest.raises(ValueError, match="WHISPERWICK_RECALL_RANK"):
        settings.recall_rank(env_path)


def recall_reply(words):
    return {"action": "recall", "target": None, "item": None, "message": words}


LOOK = {"action": "look", "target": None, "item": None, "message": None}


def test_act_recall_then_a_real_action():
    world, s = fresh_world(), stream()
    priv, stats = private_for(s), {}
    client = FakeClient([recall_reply("knife"), LOOK])
    result = llm_agent.act(world, "npc_bob", client, [], stats, private=priv)
    assert result.ok and result.observation is not None  # the look happened
    first, second = client.calls
    assert "recall" in first["schema"]["properties"]["action"]["enum"]
    assert "recall (message = words" in first["messages"][0]["content"]
    # the second ask has no recall, and shows what was found
    assert "recall" not in second["schema"]["properties"]["action"]["enum"]
    text = second["messages"][0]["content"]
    assert 'You searched your memory for "knife" and remember:' in text
    assert "- The knife lay by the well." in text
    # a recall is not a call and not a rejection
    assert stats == {"recalls": 1, "calls": 1}
    assert priv.log.records[0] == {
        "tick": world.clock.tick, "npc": "npc_bob", "kind": "recall", "when": "act",
        "words": "knife", "found": ["m0", "m1", "m3"],
    }  # fmt: skip


def test_act_recall_finding_nothing_says_so():
    client = FakeClient([recall_reply("zebra"), LOOK])
    llm_agent.act(fresh_world(), "npc_bob", client, [], {}, private=private_for(stream()))
    assert 'remember nothing about it' in client.calls[1]["messages"][0]["content"]


def test_second_recall_is_not_honoured():
    client, stats = FakeClient([recall_reply("a"), recall_reply("b")]), {}
    priv = private_for(stream())
    result = llm_agent.act(fresh_world(), "npc_bob", client, [], stats, private=priv)
    assert result.ok  # fell back to a harmless look
    assert stats["recalls"] == 1 and stats["errors"] == 1


def test_no_private_means_no_recall_offered():
    client = FakeClient([LOOK])
    llm_agent.act(fresh_world(), "npc_bob", client, [], {})
    assert "recall" not in client.calls[0]["schema"]["properties"]["action"]["enum"]


def thought(**kw):
    return {**good(), "of_what": None, "will_accuse": None, "aim": None, "aim_status": None,
            "recall": None, "notebook_me": None, "notebook_people": [], **kw}  # fmt: skip


def think(replies, s=None):
    s = s or bob_stream()
    priv, log, client = private_for(s), BeliefLog(), FakeClient(replies)
    prepared = thinking.prepare(s, "npc_bob", fresh_world(), None, log, priv)
    return client, priv, prepared, log


def test_think_without_recall_uses_the_first_reply():
    from whisperwick.thought_memory import think_all

    s = bob_stream()
    client, log, stats = FakeClient([thought()]), BeliefLog(), {}
    think_all(["npc_bob"], {"npc_bob": s}, fresh_world(), client, {}, log, 600, 1, stats,
              Notebooks(), AgentLog())  # fmt: skip
    assert len(client.calls) == 1 and "recall" in client.calls[0]["schema"]["properties"]
    assert log.records[0]["recall"] is None and log.records[0]["recalled"] == []


def test_think_with_recall_asks_twice_and_can_cite_recalled_ids():
    from whisperwick.thought_memory import think_all

    s = bob_stream()
    s.add(520, "I hid a knife under the bed.", 2)  # m3, old enough to not matter, not cited yet
    for i in range(40):  # push m3 out of the 30 recent memories shown
        s.add(530 + i, f"filler {i}", 1)
    agent_log, log, stats = AgentLog(), BeliefLog(), {}
    client = FakeClient([thought(recall="hid knife", because=["m0"]),
                         thought(because=["m3"], thoughts="The knife.")])  # fmt: skip
    think_all(["npc_bob"], {"npc_bob": s}, fresh_world(), client, {}, log, 600, 1, stats,
              Notebooks(), agent_log)  # fmt: skip
    first, second = client.calls
    assert "recall" in first["schema"]["properties"]
    assert "[m3] I hid" not in first["messages"][0]["content"]
    assert "recall" not in second["schema"]["properties"]
    assert "[m3] I hid a knife under the bed." in second["messages"][0]["content"]
    assert "m3" in second["schema"]["properties"]["because"]["items"]["enum"]
    rec = log.records[0]
    assert rec["thoughts"] == "The knife." and rec["because"][0]["memory_id"] == "m3"
    assert rec["recall"] == "hid knife" and rec["recalled"] == ["m3"]
    assert json.loads(json.dumps(rec)) == rec
    assert agent_log.records[0]["when"] == "think" and agent_log.records[0]["found"] == ["m3"]
    assert EVIDENCE in first["messages"][0]["content"]
