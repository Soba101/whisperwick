"""Aims: agent-authored, private, never assigned by code, never part of the world."""

import pytest
from helpers import fresh_world
from test_thinking import bob_stream, good, think

from whisperwick import aims, llm_agent, thinking
from whisperwick.belief_log import BeliefLog
from whisperwick.llm_client import FakeClient

AIM = "find out where Victor was last night"


def prompt(w, npc, belief):
    return llm_agent.build_messages(w, npc, belief=belief)[0]["content"]


def test_schema_has_both_required_fields():
    sch = thinking.schema(fresh_world(), "npc_bob", ["m0"])
    assert sch["properties"]["aim"] == {"type": ["string", "null"], "maxLength": 120}
    assert sch["properties"]["aim_status"] == {
        "enum": ["new", "continuing", "done", "dropped", None]
    }
    assert {"aim", "aim_status"} <= set(sch["required"])


@pytest.mark.parametrize(
    ("aim", "status", "want"),
    [
        (f"  {AIM}\n ", "new", (AIM, "new")),
        (AIM, "continuing", (AIM, "continuing")),
        (AIM, None, (AIM, "new")),  # an aim with no status is new
        (None, "new", (None, None)),  # nothing to continue
        ("", "continuing", (None, None)),
        (None, None, (None, None)),
        (AIM, "done", (AIM, "done")),
        (None, "dropped", (None, "dropped")),
        ("x" * 200, "new", ("x" * 120, "new")),
    ],
)
def test_checked_rules(aim, status, want):
    assert aims.checked({"aim": aim, "aim_status": status}) == want


def test_record_keeps_aim_and_status():
    rec, _, log, _ = think(good(aim=AIM, aim_status="new"))
    assert (rec["aim"], rec["aim_status"]) == (AIM, "new")
    assert log.latest("npc_bob") == rec


def test_bad_status_is_a_thought_error_not_a_crash():
    stats = {}
    rec, _, log, _ = think(good(aim=AIM, aim_status="soon"), stats=stats)
    assert rec is None and stats["thought_errors"] == 1 and log.records == []


def test_old_client_without_the_fields():
    rec, *_ = think(good())
    assert (rec["aim"], rec["aim_status"]) == (None, None)


def test_the_ask_is_open_and_next_thought_shows_the_aim():
    _, _, log, client = think(good(aim=AIM, aim_status="new"))
    assert "Nothing in particular is a fine answer." in client.calls[0]["messages"][1]["content"]
    sys = thinking.messages(fresh_world(), "npc_bob", None, {"m0": bob_stream().memories[0]},
                            log.latest("npc_bob"))[0]["content"]
    assert f"Your aim: {AIM}" in sys


def test_aim_is_in_own_action_prompt_only():
    w = fresh_world()
    rec = {"npc": "npc_bob", "suspect": None, "sureness": "unsure", "thoughts": "Hm.",
           "trust": [], "aim": AIM, "aim_status": "continuing"}  # fmt: skip
    assert f"What you want to do: {AIM}." in prompt(w, "npc_bob", rec)
    other = BeliefLog().latest("npc_victor")
    assert AIM not in prompt(w, "npc_victor", other)


@pytest.mark.parametrize("status", ["done", "dropped", None])
def test_over_aims_are_not_current(status):
    w = fresh_world()
    rec = {"npc": "npc_bob", "suspect": None, "sureness": "unsure", "thoughts": "Hm.",
           "trust": [], "aim": AIM, "aim_status": status}  # fmt: skip
    assert AIM not in prompt(w, "npc_bob", rec)
    assert aims.active(rec) is None


def test_thinking_does_not_change_the_world():
    w = fresh_world()
    before = w.state_hash()
    thinking.think(bob_stream(), "npc_bob", w, FakeClient([good(aim=AIM, aim_status="new")]),
                   600, None, BeliefLog())  # fmt: skip
    assert w.state_hash() == before
