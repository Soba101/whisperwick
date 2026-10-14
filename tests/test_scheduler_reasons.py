"""Turn labels explain selection without changing cooldowns or waits."""

import pytest

from whisperwick.events import Event
from whisperwick.scheduler import COOLDOWN, ROUTINE_EVERY, Scheduler

NOON = 12 * 60
NPC = "npc_bob"


@pytest.mark.parametrize(("last", "woken", "answer", "reason"), [
    (None, False, False, "first"),
    (NOON - ROUTINE_EVERY, False, False, "routine"),
    (NOON - COOLDOWN, True, False, "woken"),
    (NOON, True, True, "answer"),
    (None, True, False, "woken"),  # waking beats a first turn
    (None, True, True, "answer"),  # answering beats waking and a first turn
    (NOON - ROUTINE_EVERY, True, False, "woken"),
    (NOON - ROUTINE_EVERY, True, True, "answer"),
])
def test_reason_and_priority(last, woken, answer, reason):
    s = Scheduler([NPC])
    if last is not None:
        s.acted(NPC, last)
    if woken:
        s.notice(Event(tick=NOON - 1, type="move", actor="npc_alice",
                       location="loc_inn", witnesses=[NPC]))  # fmt: skip
    if answer:
        s.notice(Event(tick=NOON - 1, type="talk", actor="player",
                       location="loc_inn", data={"to": NPC}))  # fmt: skip
    assert s.due(NOON) == [NPC]
    assert s.reasons == {NPC: reason}


def test_reasons_only_describe_the_latest_due_list():
    s = Scheduler([NPC])
    assert s.due(NOON) == [NPC]
    s.acted(NPC, NOON)
    assert s.due(NOON + 1) == []
    assert s.reasons == {}
    assert s.due(NOON + ROUTINE_EVERY) == [NPC]
    assert s.due(22 * 60) == []
    assert s.reasons == {}


def test_events_during_a_due_list_do_not_change_its_reasons():
    s = Scheduler(["npc_alice", NPC])
    assert s.due(NOON) == ["npc_alice", NPC]
    s.acted("npc_alice", NOON)
    s.notice(Event(tick=NOON, type="talk", actor="npc_alice",
                   location="loc_inn", data={"to": NPC}))  # fmt: skip
    # Bob was selected before Alice spoke, so this is still his first turn.
    assert s.reasons[NPC] == "first"
