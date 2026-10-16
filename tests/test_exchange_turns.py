"""Real engine talks with a fake conversation writer; no network is needed."""

import pytest
from helpers import fresh_world

from whisperwick.agent_log import AgentLog
from whisperwick.llm_client import LLMError
from whisperwick.llm_sim import run_llm

A, B = "npc_bob", "npc_victor"


def exchange_reply(messages, speakers=(A, B, A)):
    return {"lines": [{"speaker": speaker, "message": message}
                      for speaker, message in zip(speakers, messages, strict=False)]}


class Conversation:
    def __init__(self, reply=None):
        self.reply = reply
        self.calls = []

    def chat(self, messages, schema):
        text = messages[0]["content"]
        exchange = "lines" in schema["properties"]
        self.calls.append((exchange, text))
        if exchange:
            if isinstance(self.reply, Exception):
                raise self.reply
            if self.reply is None:
                a = text.split("Line 1: ")[1].split()[0]
                b = B if a == A else A
                return exchange_reply(["First", "Second", "Third"], (a, b, a))
            return self.reply
        first = text.splitlines()[0]
        npc = A if f"({A})" in first else B if f"({B})" in first else None
        if npc:
            return {"action": "talk", "target": B if npc == A else A,
                    "message": f"Own line {len(self.calls)}"}
        return {"action": "look"}


def run(minutes=6, reply=None, **kwargs):
    world, client, log = fresh_world(), Conversation(reply), AgentLog()
    memories, stats = run_llm(world, client, minutes, group_turns=True, agent_log=log, **kwargs)
    talks = [e for e in world.log.all() if e.type == "talk"]
    return world, client, log.records, memories, stats, talks


def test_own_turns_surround_exchange_and_lines_keep_normal_witnesses():
    seen = []
    world, _, records, memories, stats, talks = run(
        on_event=lambda w, e: seen.append(e.id))
    start = talks[0].tick
    assert [e.actor for e in talks] == [A, B, A, B, A, B, A]
    assert [e.tick - start for e in talks] == [0, 0, 1, 2, 3, 4, 5]
    # At minute five both own directions have happened again, so a second exchange waits.
    assert [e.data["message"] for e in talks[2:5]] == ["First", "Second", "Third"]
    for e in talks[2:5]:
        assert "claim" not in e.data
        assert e.witnesses == [n for n in world.npcs_at(e.location) if n != e.actor]
        assert e.id in seen
        assert any(m.event_id == e.id for m in memories[B].memories)
    assert records[0] == {"kind": "exchange", "tick": start + 1, "npc": A, "with": B,
                          "lines": 3, "logged": 3, "event_ids": [e.id for e in talks[2:5]],
                          "dropped": None, "cut": None}
    assert stats["exchanges"] == 1 and stats["exchange_lines"] == 3
    assert stats["exchange_cut"] == 0
    assert stats["turn_reasons"]["exchange"] == 1


@pytest.mark.parametrize("reply", [{}, {"lines": []}, exchange_reply([" "]),
                                   {"lines": [1]}, {"lines": ["a"] * 4},
                                   exchange_reply(["Wrong"], (B,)),
                                   LLMError("offline")])
def test_bad_reply_falls_back_in_the_same_minute(reply):
    _, _, records, _, stats, talks = run(2, reply)
    assert talks[-1].actor == A and talks[-1].tick == talks[0].tick + 1
    assert talks[-1].data["message"].startswith("Own line")
    assert stats["exchange_failed"] == stats["turn_reasons"]["exchange"] == 1
    assert stats["turn_reasons"]["answer"] == 1
    assert records[0]["logged"] == 0 and records[0]["dropped"] == "bad reply"


@pytest.mark.parametrize("reply,logged", [(exchange_reply(["First", "x" * 501, "Third"]), 1),
                                        (exchange_reply(["x" * 501]), 0)])
def test_engine_rejection_drops_remaining_lines(reply, logged):
    _, _, records, _, stats, talks = run(5, reply)
    assert records[0]["logged"] == logged
    assert records[0]["dropped"].startswith("rejected:")
    assert stats["exchange_dropped"] >= 1
    assert not any(e.data["message"] == "Third" for e in talks)
    assert any(e.data["message"].startswith("Own line") for e in talks[2 + logged:])


class Interrupt:
    def __init__(self, actor):
        self.actor = actor
        self.minute = 0

    def turn(self, world):
        self.minute += 1
        if self.minute == 3:
            return [{"actor": self.actor, "action": "talk", "target": A, "message": "Wait!"}]
        return []

    def report(self, intent, result):
        assert result.ok


def test_player_interrupts_before_next_queued_line():
    _, _, records, _, stats, talks = run(4, player=Interrupt("player"))
    assert records[0]["dropped"] == "interrupted" and records[0]["logged"] == 1
    assert stats["exchange_dropped"] == 1
    assert not any(e.data["message"] in ("Second", "Third") for e in talks)


def test_off_is_identical_to_default():
    a, b = fresh_world(), fresh_world()
    _, sa = run_llm(a, Conversation(), 10)
    _, sb = run_llm(b, Conversation(), 10, group_turns=False)
    assert a.state_hash() == b.state_hash() and sa == sb


def test_each_new_exchange_needs_two_fresh_own_talks():
    _, client, records, _, _, talks = run(10)
    assert [r["npc"] for r in records] == [A, B]
    assert [r["tick"] - talks[0].tick for r in records] == [1, 6]
    # The two own lines between exchanges switch who opens the next exchange.
    assert all(e.data["message"].startswith("Own line") for e in talks[5:7])
    assert [e.actor for e in talks[7:10]] == [B, A, B]
    assert sum(exchange for exchange, _ in client.calls) == 2


@pytest.mark.parametrize("lines,actors", [(["One"], [A]), (["One", "Two"], [A, B]),
                                       (["One", " ", "Three"], [A])])
def test_short_exchange_still_gets_a_next_minute_own_answer(lines, actors):
    _, _, records, _, _, talks = run(2 + len(actors), exchange_reply(lines))
    assert records[0]["logged"] == len(actors)
    assert [e.actor for e in talks[2:2 + len(actors)]] == actors
    assert talks[-1].actor != actors[-1]
    assert talks[-1].tick == talks[-2].tick + 1
    assert talks[-1].data["message"].startswith("Own line")


def test_queued_lines_wake_a_bystander_who_can_cut_in():
    world, client, log = fresh_world(), Conversation(), AgentLog()
    third = "npc_alice"
    world.npcs[third].location = world.npcs[A].location
    start = world.clock.tick
    original = client.chat

    def chat(messages, schema):
        first = messages[0]["content"].splitlines()[0]
        if "lines" in schema["properties"]:
            return original(messages, schema)
        if world.clock.tick == start:
            return {"action": "look"}
        if f"({third})" in first:
            return {"action": "talk", "target": A, "message": "Bystander cuts in"}
        return original(messages, schema)

    class Wake:
        def turn(self, w):
            if w.clock.tick == start + 1:
                return [{"actor": "player", "action": "talk", "target": A, "message": "Hello"}]
            return []

        def report(self, intent, result):
            assert result.ok

    client.chat = chat
    run_llm(world, client, 7, group_turns=True, agent_log=log, player=Wake())
    record = log.records[0]
    assert record["tick"] == start + 4 and record["logged"] == 2
    assert record["dropped"] == "interrupted"
    assert any(e.actor == third and e.tick == start + 5 for e in world.log.all())


@pytest.mark.parametrize("message,speaker,cut", [("Wrong voice", A, "wrong speaker"),
                                                 (" ", B, "blank")])
def test_invalid_second_slot_keeps_only_first_line(message, speaker, cut):
    reply = exchange_reply(["First", message, "Third"], (A, speaker, A))
    _, _, records, _, stats, talks = run(3, reply)
    assert records[0]["lines"] == records[0]["logged"] == 1
    assert records[0]["cut"] == cut and records[0]["dropped"] is None
    assert stats["exchange_cut"] == 1 and stats["exchange_failed"] == 0
    assert talks[2].actor == A and talks[2].data["message"] == "First"
    assert talks[3].actor == B and talks[3].data["message"].startswith("Own line")


@pytest.mark.parametrize("message,speaker,cut", [("Wrong voice", B, "wrong speaker"),
                                                 (" ", A, "blank")])
def test_invalid_first_slot_logs_cut_and_falls_back(message, speaker, cut):
    _, _, records, _, stats, talks = run(2, exchange_reply([message], (speaker,)))
    assert records[0]["cut"] == cut and records[0]["dropped"] == "bad reply"
    assert stats["exchange_cut"] == stats["exchange_failed"] == 1
    assert talks[-1].actor == A and talks[-1].data["message"].startswith("Own line")
