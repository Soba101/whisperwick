"""Scheduler tests. Pure code, so no world and no model are needed."""

from whisperwick.clock import Clock
from whisperwick.events import Event
from whisperwick.scheduler import COOLDOWN, ROUTINE_EVERY, Scheduler

IDS = ["npc_carol", "npc_alice", "npc_bob"]
NOON = Clock.at(1, 12).tick  # well inside waking hours


def talk(tick, actor="npc_alice", to="npc_bob", witnesses=()):
    data = {"to": to, "message": "hi"}
    return Event(tick=tick, type="talk", actor=actor, location="loc_inn", data=data,
                 witnesses=list(witnesses))  # fmt: skip


def test_everyone_is_due_at_first_then_routine_every_hour():
    s = Scheduler(IDS)
    assert s.due(NOON) == ["npc_alice", "npc_bob", "npc_carol"]  # sorted, never decided
    for npc in IDS:
        s.acted(npc, NOON)
    assert s.due(NOON + ROUTINE_EVERY - 1) == []
    assert s.due(NOON + ROUTINE_EVERY) == ["npc_alice", "npc_bob", "npc_carol"]


def test_talk_wakes_target_and_witnesses_but_not_actor():
    s = Scheduler(IDS)
    for npc in IDS:
        s.acted(npc, NOON)
    s.notice(talk(NOON, witnesses=["npc_carol", "npc_alice"]))
    # Alice acted, so she stays asleep to the scheduler. Bob (target) and Carol (witness) wake.
    assert s.due(NOON + COOLDOWN) == ["npc_bob", "npc_carol"]


def test_cooldown_blocks_immediate_rewake():
    s = Scheduler(IDS)
    s.acted("npc_bob", NOON)
    s.notice(talk(NOON + 1))  # wakes bob, who only just decided
    assert "npc_bob" not in s.due(NOON + 1)
    assert "npc_bob" in s.due(NOON + COOLDOWN)


def test_acted_clears_the_woken_flag():
    s = Scheduler(IDS)
    s.acted("npc_bob", NOON)
    s.notice(talk(NOON + 10))
    s.acted("npc_bob", NOON + 10)
    assert "npc_bob" not in s.due(NOON + 10 + COOLDOWN)


def test_nobody_is_due_at_night_and_wakeups_are_dropped():
    s = Scheduler(IDS)
    for hour in (22, 23, 0, 3, 5):
        assert s.asleep(Clock.at(1, hour).tick)
        assert s.due(Clock.at(1, hour).tick) == []
    assert not s.asleep(Clock.at(1, 6).tick)
    assert not s.asleep(Clock.at(1, 21, 59).tick)
    for npc in IDS:
        s.acted(npc, Clock.at(1, 21).tick)
    s.notice(talk(Clock.at(1, 23).tick))  # night: dropped
    morning = Clock.at(2, 6, 0).tick
    assert s.due(morning) == ["npc_alice", "npc_bob", "npc_carol"]  # routine, not a stale wake


def test_scheduler_only_schedules_the_ids_it_is_given():
    """The run loop hands it living NPCs only, so a dead one is never due or woken."""
    s = Scheduler(["npc_alice", "npc_bob"])  # npc_mayor is dead, so not passed in
    s.notice(talk(NOON, to="npc_mayor", witnesses=["npc_mayor"]))
    assert s.due(NOON) == ["npc_alice", "npc_bob"]
    assert "npc_mayor" not in s.woken
