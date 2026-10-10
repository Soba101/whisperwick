"""Belief, intention and speech are three separate records (#35, #36)."""

from helpers import fresh_world
from scene import belief, new_world, talk

from whisperwick import llm_agent, thinking
from whisperwick.belief_log import BeliefLog
from whisperwick.belief_text import belief_lines
from whisperwick.events import Event
from whisperwick.llm_client import FakeClient
from whisperwick.memory import Memories, MemoryStream
from whisperwick.story import format_story
from whisperwick.trace import own_claims

TALK = {"action": "talk", "target": "npc_bob", "item": None, "accuses": None, "defends": None}
THOUGHT = {
    "thoughts": "It was me.", "suspect": "npc_victor", "of_what": "a bad thing",
    "sureness": "certain", "will_accuse": "npc_hal", "because": ["m0"], "trust": [],
}  # fmt: skip


def victor_thinks(reply=THOUGHT, stats=None):
    stream = MemoryStream()
    stream.add(480, "I did something.", 9, "evidence")
    log = BeliefLog()
    rec = thinking.think(
        stream, "npc_victor", fresh_world(), FakeClient([reply]), 500, None, log, stats
    )
    return rec, log


def test_belief_intention_and_speech_are_three_separate_records():
    world = fresh_world()
    rec, log = victor_thinks()
    # 1. private belief and 2. intended accusation differ, both stored.
    assert rec["suspect"] == "npc_victor" and rec["will_accuse"] == "npc_hal"
    # 3. what he then says: the tag follows his words, and the words mention Hal.
    say = {**TALK, "target": "npc_bob", "message": "Hal did it", "accuses": "npc_hal"}
    result = llm_agent.act(world, "npc_victor", FakeClient([say]), belief=log.latest("npc_victor"))
    assert result.event.data["claim"] == {"kind": "accuses", "subject": "npc_hal"}
    assert "unverified" not in result.event.data["claim"]
    # The prompt line for his own next turn shows the intention beside the belief.
    assert "You mean to accuse Hal (npc_hal) out loud." in "\n".join(
        belief_lines(world, rec, "npc_victor")
    )


def test_both_set_keeps_accuses_and_counts_it():
    stats = {}
    both = {**TALK, "message": "hi", "accuses": "npc_hal", "defends": "npc_victor"}
    got = llm_agent.decide(fresh_world(), "npc_victor", FakeClient([both]), stats=stats)
    assert got.claim.kind == "accuses" and got.claim.subject == "npc_hal"
    assert stats["claim_both"] == 1
    # A non-talk drops both silently and counts nothing.
    stats = {}
    look = {**both, "action": "look", "target": None}
    got = llm_agent.decide(fresh_world(), "npc_victor", FakeClient([look]), stats=stats)
    assert got.claim is None and "claim_both" not in stats


def test_name_check_flags_a_tag_the_words_never_mention():
    world, memories, _ = new_world()
    hal = {"kind": "accuses", "subject": "npc_hal"}
    e = talk(world, memories, "npc_bob", "npc_alice", "It was dark last night.", hal)
    assert e.data["claim"] == {**hal, "unverified": True}
    assert e.data["message"] == "It was dark last night."  # words never change
    # The listener hears only the words, no tag.
    assert "[claim" not in memories["npc_alice"].memories[0].text
    # The story shows it, marked, for analysis.
    assert "[claim: accuses npc_hal] (unverified tag)" in format_story([e], {})
    # A word of the display name or the id is enough, case-insensitive.
    ok = talk(world, memories, "npc_bob", "npc_alice", "I saw HAL there", hal)
    assert "unverified" not in ok.data["claim"]
    ok = talk(world, memories, "npc_bob", "npc_alice", "npc_hal was there", hal)
    assert "unverified" not in ok.data["claim"]
    # Whole words only: "shall" is not "Hal".
    bad = talk(world, memories, "npc_bob", "npc_alice", "We shall see", hal)
    assert bad.data["claim"]["unverified"] is True


def test_old_logs_with_killer_and_innocent_still_read():
    world, _, _ = new_world()
    old = Event(
        id=1, tick=480, type="talk", actor="npc_bob", location="loc_market",
        data={"to": "npc_alice", "message": "Hal did it",
              "claim": {"kind": "killer", "subject": "npc_hal"}},
        witnesses=["npc_alice"],
    )  # fmt: skip
    mem = Memories()
    mem.observe(old, world)
    assert "[claim: accuses Hal (npc_hal)]" in mem["npc_alice"].memories[0].text
    assert "[claim: accuses Hal]" in format_story([old], {"npc_hal": "Hal"})
    assert own_claims([old], BeliefLog()) == [old]
    cleared = old.model_copy(
        update={"data": {**old.data, "claim": {"kind": "innocent", "subject": "npc_hal"}}}
    )
    assert "defends" in format_story([cleared], {})
    assert own_claims([cleared], BeliefLog()) == []


def test_will_accuse_unknown_is_an_error_and_missing_is_none():
    stats = {}
    rec, _ = victor_thinks({**THOUGHT, "will_accuse": "npc_nobody"}, stats)
    assert rec is None and stats["thought_errors"] == 1
    old = {k: v for k, v in THOUGHT.items() if k != "will_accuse"}
    rec, _ = victor_thinks(old)
    assert rec["will_accuse"] is None
    # Old records without the key still make prompt lines.
    assert belief_lines(fresh_world(), belief("npc_bob", 0), "npc_bob")
