"""Eligibility and privacy depend on event facts, never private memory words."""

import pytest
from helpers import fresh_world

from whisperwick.agent_log import AgentLog
from whisperwick.exchange_prompt import SCHEMA, build_messages, parse_lines
from whisperwick.exchange_queue import Exchanges
from whisperwick.llm_sim import run_llm
from whisperwick.memory import Memories
from whisperwick.repeat_guard import ActionHistory
from whisperwick.scheduler import Scheduler

A, B, C = "npc_bob", "npc_victor", "npc_alice"


def setup():
    world = fresh_world()
    scheduler, memories, stats, log = Scheduler([A, B, C]), Memories(), {}, AgentLog()
    stats["turn_reasons"] = {"exchange": 0}
    queue = Exchanges(world, scheduler, memories, stats, log, {}, ActionHistory(), None)
    return world, scheduler, memories, stats, log, queue


def say(world, queue, a, b, own=True):
    result = world.act({"actor": a, "action": "talk", "target": b, "message": "Hello"})
    assert result.ok
    queue.observe(result.event, own=own)
    return result.event


def test_only_own_talks_to_each_other_unlock_a_pair():
    world, _, _, _, _, queue = setup()
    say(world, queue, A, B)
    assert queue.eligible(B, "answer") is None
    say(world, queue, B, A, own=False)
    assert queue.eligible(A, "answer") is None
    say(world, queue, B, A)
    assert queue.eligible(A, "answer") == B
    assert queue.eligible(A, "woken") is None
    say(world, queue, "player", A)
    assert queue.eligible(A, "answer") is None


@pytest.mark.parametrize("change", ["held_a", "held_b", "dead", "apart", "night"])
def test_ineligible_pairs_and_pending_pairs_are_checked_again(change):
    world, _, _, stats, log, queue = setup()
    say(world, queue, A, B)
    say(world, queue, B, A)

    class Client:
        def chat(self, messages, schema):
            return {"lines": ["One", "Two", "Three"]}

    assert queue.begin(A, B, Client())
    if change.startswith("held"):
        world.npcs[A if change == "held_a" else B].held_by = "npc_hal"
    elif change == "dead":
        world.npcs[B].alive = False
    elif change == "apart":
        world.npcs[B].location = "loc_inn"
    else:
        world.clock.tick = 22 * 60
    assert queue.eligible(A, "answer") is None
    queue.start_minute()
    assert not queue.pending and not queue.blocked
    assert stats["exchange_dropped"] == 1
    assert log.records[0]["logged"] == 1


def test_third_villager_talk_cancels_queue_and_releases_speakers():
    from test_exchange_turns import Conversation

    world, _, _, _, log, queue = setup()
    world.npcs[C].location = world.npcs[A].location
    say(world, queue, A, B)
    say(world, queue, B, A)
    queue.begin(A, B, Conversation())
    say(world, queue, C, A)
    assert not queue.pending and not queue.blocked
    assert log.records[0]["dropped"] == "interrupted"


def test_prompt_uses_shared_event_ids_and_neutral_words_only():
    from test_exchange_turns import Conversation

    world, _, memories, _, _, queue = setup()
    # Neither hand-written memories nor starting evidence are shared event facts.
    memories[A].add(world.clock.tick, "PRIVATE_MEMORY_TOKEN", 9)
    shared = say(world, queue, A, B)
    memories[A].add(world.clock.tick, "REWRITTEN_MEMORY_TOKEN", 9, event_id=shared.id)
    # A heard this event while B was elsewhere. Later co-location cannot make it shared.
    world.npcs[B].location = "loc_inn"
    private = world.act({"actor": "player", "action": "talk", "target": A,
                         "message": "PRIVATE_EVENT_TOKEN"}).event
    assert private is not None
    world.npcs[B].location = world.npcs[A].location
    client = Conversation()
    run_llm(world, client, 2, memories=memories, group_turns=True,
            evidence={A: ["PRIVATE_EVIDENCE_TOKEN"]}, personalities={A: "Patient"})
    prompts = [text for exchange, text in client.calls if exchange]
    assert prompts
    text = prompts[0]
    for secret in ("PRIVATE_MEMORY_TOKEN", "PRIVATE_EVIDENCE_TOKEN", "PRIVATE_EVENT_TOKEN",
                   "REWRITTEN_MEMORY_TOKEN"):
        assert secret not in text
    assert f"Event {shared.id}:" in text
    assert "Bob (npc_bob) said to Victor (npc_victor)" in text
    assert "Patient" in text
    assert "claim" not in str(SCHEMA)


def test_shared_events_limit_and_blank_lines():
    world, _, _, _, _, queue = setup()
    for _ in range(23):
        say(world, queue, A, B)
    text = build_messages(world, A, B, {})[0]["content"]
    assert "Event 3:" not in text and "Event 4:" in text
    assert text.count("Event ") == 20
    assert parse_lines({"lines": ["  One  ", " ", "Two"]}) == ["One", "Two"]
