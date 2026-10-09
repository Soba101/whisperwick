"""Issue #12: the repeat guard refuses the same show, give, claim or message within 2 hours."""

from helpers import fresh_world

from whisperwick import llm_agent
from whisperwick.actions import Claim, Intent
from whisperwick.llm_client import FakeClient
from whisperwick.llm_sim import run_llm
from whisperwick.repeat_guard import REPEAT_WINDOW, ActionHistory

LOOK = {"action": "look", "target": None, "item": None, "message": None}


def show(item="item_knife", target=None):
    return {"action": "show", "target": target, "item": item, "message": None}


def talk(message="hello", claim=None):
    reply = {"action": "talk", "target": "npc_victor", "item": None, "message": message}
    if claim:
        reply.update(claim_kind=claim[0], claim_subject=claim[1])
    return reply


def hal_with_knife():
    w = fresh_world()
    w.act(Intent(actor="npc_hal", action="take", item="item_knife"))
    return w


def test_same_show_is_rejected_then_allowed_after_the_window():
    w = hal_with_knife()
    h, stats = ActionHistory(), {}
    assert llm_agent.act(w, "npc_hal", FakeClient([show()]), stats=stats, history=h).ok
    w.clock.advance(10)
    # Two repeats in a row: the retry repeats too, so the turn falls back to look.
    result = llm_agent.act(w, "npc_hal", FakeClient([show(), show()]), stats=stats, history=h)
    assert result.observation is not None  # fell back to look
    assert stats["repeats"] == 2 and stats["rejected"] == 2
    w.clock.advance(REPEAT_WINDOW)  # now more than 2 hours after the first show
    assert llm_agent.act(w, "npc_hal", FakeClient([show()]), stats=stats, history=h).ok
    assert stats["repeats"] == 2


def test_feedback_names_what_was_done_and_when():
    w = hal_with_knife()
    h = ActionHistory()
    llm_agent.act(w, "npc_hal", FakeClient([show()]), history=h)
    w.clock.advance(5)
    client = FakeClient([show(), LOOK])
    llm_agent.act(w, "npc_hal", client, history=h)
    # The second prompt carries the repeat reason as feedback.
    text = client.calls[1]["messages"][0]["content"]
    assert "you already showed bloody knife to everyone here at day 1 08:00" in text
    assert "do something new" in text


def test_show_to_a_different_target_or_item_is_fine():
    w = hal_with_knife()
    h = ActionHistory()
    assert llm_agent.act(w, "npc_hal", FakeClient([show()]), history=h).ok

    def asks(**kw):
        return h.find_repeat(w.clock.tick, Intent(actor="npc_hal", action="show", **kw))

    assert asks(item="item_knife", target=None) is not None  # same audience: a repeat
    assert asks(item="item_knife", target="npc_sarah") is None  # a named person is new
    assert asks(item="item_boots", target=None) is None  # another item is new


def test_same_message_is_rejected_even_with_different_case_and_spaces():
    w = fresh_world()
    h, stats = ActionHistory(), {}
    assert llm_agent.act(
        w, "npc_bob", FakeClient([talk("Hello  there")]), stats=stats, history=h
    ).ok
    w.clock.advance(1)
    r = llm_agent.act(w, "npc_bob", FakeClient([talk("hello THERE"), LOOK]), stats=stats, history=h)
    assert r.observation is not None and stats["repeats"] == 1


def test_same_claim_with_new_words_is_still_a_repeat():
    w = fresh_world()
    h, stats = ActionHistory(), {}
    claim = ("killer", "npc_hal")
    assert llm_agent.act(w, "npc_bob", FakeClient([talk("a", claim)]), stats=stats, history=h).ok
    w.clock.advance(1)
    # Retry with a different claim succeeds: the guard only blocks the same one.
    r = llm_agent.act(
        w, "npc_bob", FakeClient([talk("b", claim), talk("c", ("innocent", "npc_hal"))]),
        stats=stats, history=h,
    )  # fmt: skip
    assert r.ok and stats["repeats"] == 1 and stats["rejected"] == 1
    reason = llm_agent.repeat_reason(
        w, h, Intent(actor="npc_bob", action="talk", target="npc_victor", message="d",
                     claim=Claim(kind="innocent", subject="npc_hal")),
    )  # fmt: skip
    assert "told Victor (npc_victor) that Hal (npc_hal) is innocent" in reason


def test_guard_is_per_actor():
    w = fresh_world()
    h = ActionHistory()
    assert llm_agent.act(w, "npc_bob", FakeClient([talk("same")]), history=h).ok
    same = Intent(actor="npc_bob", action="talk", target="npc_victor", message="same")
    other = same.model_copy(update={"actor": "npc_alice"})
    assert h.find_repeat(w.clock.tick, same) is not None
    assert h.find_repeat(w.clock.tick, other) is None  # Alice saying it is not Bob repeating


def test_no_history_means_no_guard():
    w = fresh_world()
    stats = {}
    for _ in range(2):
        assert llm_agent.act(w, "npc_bob", FakeClient([talk("same")]), stats=stats).ok
    assert "repeats" not in stats


def test_run_counts_repeats_and_blocks_repeated_talk():
    w = fresh_world()

    class Parrot:
        def chat(self, messages, schema):
            if "thoughts" in schema["properties"]:
                return {"thoughts": "quiet"}
            if "(npc_bob)" in messages[0]["content"]:
                return talk("same words")
            return {**LOOK, "claim_kind": None, "claim_subject": None}

    stats = {}
    # Bob is due every hour; over 3 hours he may say it once, then the guard steps in.
    run_llm(w, Parrot(), 180, stats=stats)
    said = [e for e in w.log.all() if e.type == "talk" and e.actor == "npc_bob"]
    assert len(said) == 2  # 08:00 and again once the 2-hour window has passed (10:00)
    assert stats["repeats"] >= 1
