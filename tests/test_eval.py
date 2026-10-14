"""`whisperwick eval`: code-only measures and the summary. No model, no network."""

import json
from pathlib import Path

from eval_helpers import make_run, strip_week6
from typer.testing import CliRunner

from whisperwick import cli, eval_measures, llm_run
from whisperwick.compare import load_run
from whisperwick.eval_loop import loop_measures
from whisperwick.eval_stall import authority_of, stall_measures
from whisperwick.events import Event
from whisperwick.player import PLAYER_ID


def measure(db):
    return eval_measures.measure(load_run(Path(db)), Path(db))


def test_measures_for_one_run(tmp_path):
    m = measure(make_run(tmp_path))
    assert m["script"] == "none" and m["seed"] == 1 and m["memory"] is True
    assert m["days"] == 120 / 1440
    # Bob (innocent) is held; the secret murderer is Victor.
    assert m["held"] == ["npc_bob"] and m["verdict"] == "wrong"
    assert m["arrests"] == 1 and m["releases"] == 0
    # Two talks (08:00, 09:00) and the added arrest.
    assert m["talk_share"] == 2 / 3 and m["calls"] > 0
    assert m["recalls"] == {"act": 2, "think": 1}
    # One of the two suspect thoughts cites a memory.
    assert m["valid_share"] == 0.5 and m["suspect_thoughts"] == 2
    assert m["aims"]["new"] == 2 and m["judge"] is None


def test_verdicts():
    assert eval_measures.verdict([], "npc_victor") == "nobody"
    assert eval_measures.verdict(["npc_victor"], "npc_victor") == "right"
    assert eval_measures.verdict(["npc_victor", "npc_bob"], "npc_victor") == "mixed"
    assert eval_measures.verdict(["npc_bob"], "npc_victor") == "wrong"


def test_stalls_count_awake_hours_without_villager_events(tmp_path):
    # Two hours played from 08:00 and Bob talks every hour, so no stall.
    assert measure(make_run(tmp_path))["stalls"] == 0
    # A sidecar claiming a long run leaves later awake hours empty.
    db = make_run(tmp_path, name="long")
    p = llm_run.sidecar_path(db)
    d = json.loads(p.read_text())
    d["minutes"] = 6 * 60
    p.write_text(json.dumps(d))
    assert measure(db)["stalls"] == 3  # 08-10 have events (the arrest is at 10:00); 11-13 are empty


def test_week5_sidecar_still_works(tmp_path):
    db = make_run(tmp_path, memory=False)
    strip_week6(db)
    m = measure(db)
    assert m["seed"] is None and m["memory"] is False and m["recalls"] is None
    out = CliRunner().invoke(cli.app, ["eval", db])
    assert out.exit_code == 0, out.output
    assert "Bob (wrong)" in out.output and "off" in out.output


def test_eval_summary_divergence_and_memory(tmp_path):
    dbs = [
        make_run(tmp_path, "a1", "none", seed=1, memory=True, arrest="npc_bob"),
        make_run(tmp_path, "a2", "blame_hal", seed=1, memory=True, arrest="npc_victor"),
        make_run(tmp_path, "b1", "none", seed=2, memory=False, arrest="npc_bob"),
        make_run(tmp_path, "b2", "blame_hal", seed=2, memory=False, arrest="npc_bob"),
    ]
    out = CliRunner().invoke(cli.app, ["eval", *dbs])
    assert out.exit_code == 0, out.output
    # Seed 1 ends differently by script, seed 2 does not.
    assert "Seeds where the outcome differs by script: 1/2 = 50%" in out.output
    assert "Memory on versus off" in out.output
    assert "on" in out.output.split("Memory on versus off")[1]
    assert "(right)" in out.output and "(wrong)" in out.output


def test_missing_db_is_a_clean_error(tmp_path):
    out = CliRunner().invoke(cli.app, ["eval", str(tmp_path / "nope.db")])
    assert out.exit_code == 1 and "No such file" in out.output


def test_divergence_keeps_memory_on_and_off_apart():
    # A memory-off baseline ending differently must not count as a script making a difference.
    from whisperwick.eval_summary import divergence

    def run(script, memory, held):
        return {"seed": 2, "memory": memory, "script": script, "held": held}

    ms = [run("none", True, ["npc_victor"]), run("blame_hal", True, ["npc_victor"]),
          run("none", False, [])]  # fmt: skip
    assert divergence(ms)[-1] == "Seeds where the outcome differs by script: 0/1 = 0%"


def _talk(tick, actor, kind="accuses", subject="npc_victor", to="npc_x"):
    claim = {"kind": kind, "subject": subject} if kind else None
    return Event(tick=tick, type="talk", actor=actor, location="loc_inn",
                 data={"message": "m", "to": to, "claim": claim})  # fmt: skip


def _ev(tick, type_, actor="npc_bob"):
    return Event(tick=tick, type=type_, actor=actor, location="loc_inn")


def test_loop_measures_after_arrest():
    events = [
        _talk(10, "npc_bob"),  # before the arrest: makes this claim old for Bob
        _ev(100, "arrest", "npc_hal"),
        _talk(110, "npc_bob"),  # repeat of an old claim: not new
        _talk(120, "npc_alice"),  # same claim, different speaker: new
        _talk(130, "npc_alice"),  # Alice repeating herself: not new
        _talk(140, "npc_bob", kind=None),  # no claim: skipped
        _talk(150, "npc_bob", subject="npc_hal"),  # a different subject: new
        _ev(160, "move"),
        _ev(170, "look"),  # looking changes nothing
        _ev(180, "take", PLAYER_ID),  # the player is not a villager
    ]
    m = loop_measures(events, 100 + 1440)  # exactly one day after the arrest
    assert m["new_claims_after_arrest"] == 2
    assert m["new_claims_per_day"] == 2.0
    assert m["not_talk_after_arrest"] == 1
    assert m["events_after_arrest"] == 7
    # Pairs after the arrest: bob->x 3, alice->x 2, so both pairs cover all 5 talks.
    assert m["top_pair_share"] == 1.0
    # Last new claim at 150 (02:30), run end at 1540 (01:40 next day). Between them only
    # 06:00-22:00 of day one counts, so the gap is 16 waking hours, not 23.
    assert m["longest_claim_gap_hours"] == 16.0


def test_loop_measures_none_without_arrest():
    m = loop_measures([_talk(10, "npc_bob")], 1440)
    assert set(m.values()) == {None}


def test_loop_measures_late_last_arrest_has_no_claim_gap():
    # An earlier arrest gives plenty of time, but only the last arrest sets the window.
    arrest = 3 * 1440 + 7 * 60 + 16
    events = [_ev(360, "arrest"), _ev(arrest, "arrest"), _ev(arrest + 10, "move")]
    m = loop_measures(events, arrest + 60)
    assert m["longest_claim_gap_hours"] is None
    assert m["new_claims_after_arrest"] == 0 and m["new_claims_per_day"] == 0
    assert m["not_talk_after_arrest"] == 1 and m["events_after_arrest"] == 1
    assert m["top_pair_share"] is None
    # A whole calendar day is still too short if it lacks a full waking day.
    assert loop_measures([_ev(22 * 60, "arrest")], 1440 + 21 * 60)[
        "longest_claim_gap_hours"
    ] is None


# Guard stall: pure function, authority/start/end passed in. Day 1 starts at tick 0 here, so
# waking hours are ticks 360-1320 of each 1440-minute day.
def test_stall_arrest_closes_case_early():
    events = [_ev(420, "move", "npc_hal"), _ev(480, "arrest", "npc_hal")]
    m = stall_measures(events, ["npc_hal"], 360, 360 + 3 * 1440)
    assert m["guard_stall_hours"] == 1.0  # 07:00 to 08:00, the days after do not count
    assert m["guard_acts_open"] == 2


def test_stall_no_arrest_runs_to_the_end():
    m = stall_measures([_ev(400, "take", "npc_hal")], ["npc_hal"], 360, 360 + 960)
    assert m["guard_stall_hours"] == (960 - 40) / 60  # whole awake day minus the first 40 min
    assert m["guard_acts_open"] == 1


def test_stall_night_minutes_do_not_count():
    # 21:00 on day 1 to 07:00 on day 2: one waking hour (21-22) plus one (06-07).
    events = [_ev(21 * 60, "move", "npc_hal"), _ev(1440 + 7 * 60, "move", "npc_hal")]
    m = stall_measures(events, ["npc_hal"], 21 * 60, 1440 + 7 * 60)
    assert m["guard_stall_hours"] == 2.0


def test_stall_talk_does_not_break_it():
    events = [_talk(500, "npc_hal"), _talk(600, "npc_hal")]
    m = stall_measures(events, ["npc_hal"], 480, 480 + 600)
    assert m["guard_stall_hours"] == 10.0
    assert m["guard_acts_open"] == 0


def test_stall_ignores_non_arresters():
    m = stall_measures([_ev(500, "move", "npc_bob")], ["npc_hal"], 480, 480 + 600)
    assert m["guard_stall_hours"] == 10.0
    assert m["guard_acts_open"] == 0


def test_stall_none_without_scenario():
    assert authority_of({"scenario": "/no/such/file.yaml"}) == []
    m = stall_measures([], [], 0, 100)
    assert m["guard_stall_hours"] is None
