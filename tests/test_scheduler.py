"""Scheduler tests. Pure code, so no world and no model are needed."""

from whisperwick.clock import Clock
from whisperwick.events import Event
from whisperwick.scheduler import ANSWER_WAIT, COOLDOWN, ROUTINE_EVERY, Scheduler

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
    # Alice spoke to the dead mayor, so she waits for an answer that never comes.
    assert s.due(NOON) == ["npc_bob"]
    assert "npc_mayor" not in s.woken and "npc_mayor" not in s.answer_at


def settle(s, tick):
    """Everyone has just decided at this tick."""
    for npc in IDS:
        s.acted(npc, tick)


def test_spoken_to_answers_next_minute_despite_cooldown():
    s = Scheduler(IDS)
    settle(s, NOON)
    s.notice(talk(NOON + 1, actor="npc_alice", to="npc_bob"))
    assert s.due(NOON + 1) == []  # same minute: not yet
    assert s.due(NOON + 2) == ["npc_bob"]  # cooldown (5) ignored


def test_speaker_waits_until_target_does_anything():
    s = Scheduler(IDS)
    settle(s, NOON)
    s.notice(talk(NOON + 1, actor="npc_alice", to="npc_bob"))
    assert "npc_alice" not in s.due(NOON + 3)
    move = Event(tick=NOON + 3, type="move", actor="npc_bob", location="loc_inn",
                 data={}, witnesses=["npc_alice"])  # fmt: skip
    s.notice(move)
    # Released by any event from Bob, and she saw it, so the wake-up counts again.
    assert s.waiting == {}
    assert "npc_alice" in s.due(NOON + 1 + COOLDOWN)


def test_speaker_gives_up_after_answer_wait():
    s = Scheduler(IDS)
    settle(s, NOON)
    s.notice(talk(NOON + 1, actor="npc_alice", to="npc_bob"))
    assert "npc_alice" not in s.due(NOON + 1 + ANSWER_WAIT - 1)
    s.notice(talk(NOON + 1 + ANSWER_WAIT - 1, actor="npc_carol", to=None, witnesses=["npc_alice"]))
    assert "npc_alice" not in s.due(NOON + 1 + ANSWER_WAIT - 1)  # wake-up held back too
    assert "npc_alice" in s.due(NOON + 1 + ANSWER_WAIT)


def test_being_spoken_to_beats_waiting():
    s = Scheduler(IDS)
    settle(s, NOON)
    s.notice(talk(NOON + 1, actor="npc_alice", to="npc_bob"))
    s.notice(talk(NOON + 2, actor="npc_carol", to="npc_alice"))
    assert "npc_alice" in s.due(NOON + 3)


def test_talk_to_nobody_makes_no_one_wait():
    s = Scheduler(IDS)
    settle(s, NOON)
    s.notice(talk(NOON + 1, actor="npc_alice", to=None))
    assert "npc_alice" not in s.waiting


def test_bystanders_still_respect_cooldown():
    s = Scheduler(IDS)
    settle(s, NOON)
    s.notice(talk(NOON + 1, actor="npc_alice", to="npc_bob", witnesses=["npc_carol"]))
    assert s.due(NOON + 2) == ["npc_bob"]  # Carol overheard but is on cooldown
    assert "npc_carol" in s.due(NOON + COOLDOWN)


def test_player_is_waited_on_and_night_drops_answers():
    s = Scheduler(IDS)
    settle(s, NOON)
    s.notice(talk(NOON + 1, actor="npc_alice", to="player"))
    assert "player" not in s.answer_at and "npc_alice" in s.waiting
    s.notice(talk(NOON + 1, actor="player", to="npc_alice"))
    assert s.waiting == {} and s.answer_at == {"npc_alice": NOON + 2}
    night = Clock.at(1, 23).tick
    assert s.due(night) == []
    assert s.answer_at == {} and s.waiting == {}


def test_scripted_due_sequence_keeps_the_same_turns():
    s = Scheduler(IDS)
    assert s.due(NOON) == ["npc_alice", "npc_bob", "npc_carol"]
    settle(s, NOON)
    s.notice(talk(NOON + 1, witnesses=["npc_carol"]))
    assert s.due(NOON + 1) == []
    assert s.due(NOON + 2) == ["npc_bob"]
    s.acted("npc_bob", NOON + 2)
    s.notice(Event(tick=NOON + 2, type="move", actor="npc_bob", location="loc_inn",
                   witnesses=["npc_alice"]))  # fmt: skip
    assert s.due(NOON + 4) == []
    assert s.due(NOON + COOLDOWN) == ["npc_alice", "npc_carol"]
    s.acted("npc_alice", NOON + COOLDOWN)
    s.acted("npc_carol", NOON + COOLDOWN)
    assert s.due(NOON + 2 + ROUTINE_EVERY - 1) == []
    assert s.due(NOON + 2 + ROUTINE_EVERY) == ["npc_bob"]
    assert s.due(Clock.at(1, 22).tick) == []
    assert s.due(Clock.at(2, 6).tick) == ["npc_alice", "npc_bob", "npc_carol"]
