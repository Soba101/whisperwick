"""Belief lines in the interview summary and in compare. No model is called."""

from scene import belief, new_world, rumour

from whisperwick import compare, run_report
from whisperwick.belief_log import BeliefLog

NAMES = {"npc_bob": "Bob", "npc_alice": "Alice", "npc_hal": "Hal", "npc_victor": "Victor",
         "player": "Wren"}  # fmt: skip


def test_interview_lines_show_what_they_told_and_what_they_think():
    log = BeliefLog()
    log.add(belief("npc_bob", 0, "npc_victor"))
    log.add(belief("npc_hal", 0, None))
    answers = {
        "npc_bob": {"suspect": "npc_victor", "why": ""},
        "npc_hal": {"suspect": None, "why": ""},
        "npc_alice": {"suspect": "npc_hal", "why": ""},
    }
    assert run_report.summary_lines(answers, NAMES, log) == [
        "  Alice: told the interviewer Hal; privately suspects no thoughts logged",
        "  Bob: told the interviewer Victor; privately suspects Victor (fairly sure)",
        "  Hal: told the interviewer no idea; privately suspects nobody",
    ]


def test_interview_lines_are_unchanged_without_a_belief_log():
    answers = {"npc_bob": {"suspect": "npc_hal", "why": ""}}
    old = ["  Bob -> Hal"]
    assert run_report.summary_lines(answers, NAMES) == old
    assert run_report.summary_lines(answers, NAMES, None) == old
    assert run_report.summary_lines(answers, NAMES, BeliefLog()) == old  # nobody thought


def test_compare_shows_suspects_trust_and_counts():
    world, _, log, _, _ = rumour()
    rating = [{"person": "player", "level": "high", "why": "x"}]
    log.add(belief("npc_bob", 9, "npc_victor", sureness="certain", trust=rating))
    log.add(belief("npc_hal", 9, None))
    log.add(belief("npc_alice", 9, "npc_hal", hunch=True, because=[]))
    run = {"name": "a.db", "events": world.log.all(), "sidecar": {}, "beliefs": log}
    text = compare.format_compare([run], NAMES)
    assert "Beliefs (latest thought):" in text
    assert "Bob" in text and "Victor (certain)" in text
    assert "Alice  Hal (fairly sure)" in text  # latest record per villager
    assert "Trust in the player: Alice not rated, Bob high, Hal not rated" in text
    # 5 records; two hunches (Bob and Alice cite nothing in their last).
    # Claims by Bob and Wren; only Wren's has no source.
    assert "thoughts 5, hunches 2, claims: Bob 1, Wren 1; own-claims (no source): 1" in text


def test_compare_copes_with_a_run_that_has_no_belief_log():
    world, _ = new_world()[:2]
    old = {"name": "old.db", "events": world.log.all(), "sidecar": {}, "beliefs": None}
    no_key = {"name": "older.db", "events": [], "sidecar": {}}  # built before beliefs existed
    text = compare.format_compare([old, no_key], NAMES)
    assert "Beliefs (latest thought):" in text and "  old.db:\n    -" in text
