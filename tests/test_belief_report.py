"""Beliefs replayed from a saved run: helper, interview columns, compare, old sidecars."""

import json

from helpers import SCENARIO
from typer.testing import CliRunner

from whisperwick import belief_report, cli, compare, compare_command, run_report
from whisperwick.llm_client import FakeClient
from whisperwick.memory import Memories
from whisperwick.scenario import build_world, load_scenario
from whisperwick.story import names_from

SC = load_scenario(SCENARIO)
NAMES = names_from(SC)


def talk(w, actor, to, kind, subject):
    claim = {"kind": kind, "subject": subject}
    r = w.act({"actor": actor, "action": "talk", "target": to, "message": "psst", "claim": claim})
    assert r.ok, r.reason
    return r.event


def make_run(tmp_path, name="run.db", sidecar=True):
    """Real acts on a real world: player lies to Bob, Bob repeats it to Alice (same tick)."""
    db = tmp_path / name
    w = build_world(SC, str(db))
    talk(w, "player", "npc_bob", "killer", "npc_hal")  # the lie: no source behind it
    assert w.act({"actor": "npc_bob", "action": "move", "target": "loc_inn"}).ok
    talk(w, "npc_bob", "npc_alice", "killer", "npc_hal")  # Bob repeats it, same tick
    w.log.db.close()  # the file is now a finished run
    if sidecar:
        db.with_suffix(".json").write_text(json.dumps({"scenario": str(SCENARIO)}))
    return db


def test_beliefs_for_run_matches_the_story(tmp_path):
    state = belief_report.beliefs_for_run(make_run(tmp_path))
    assert state.confidence("npc_bob", "npc_hal") > 0
    assert state.confidence("npc_alice", "npc_hal") > 0
    assert state.sources["npc_alice"]["npc_hal"][0].by == "npc_bob"


def test_missing_or_dead_sidecar_falls_back_to_default_scenario(tmp_path):
    db = make_run(tmp_path, sidecar=False)
    assert belief_report.beliefs_for_run(db).confidence("npc_alice", "npc_hal") > 0
    # A sidecar that points at a file which is gone also falls back.
    db.with_suffix(".json").write_text(json.dumps({"scenario": "nowhere.yaml"}))
    assert belief_report.beliefs_for_run(db).confidence("npc_alice", "npc_hal") > 0


def test_interview_answers_carry_the_code_answer(tmp_path):
    state = belief_report.beliefs_for_run(make_run(tmp_path))
    client = FakeClient([{"suspect": "npc_victor", "why": "boots"}] * 5)
    out = run_report.interview.interview(
        build_world(SC), Memories(), client, ["npc_bob", "npc_hal"], {}, state
    )
    assert out["npc_bob"]["belief_suspect"] == "npc_victor"  # Bob's own sighting still leads
    assert out["npc_bob"]["belief_confidence"] == 0.5
    assert out["npc_hal"]["belief_suspect"] is None  # Hal heard nothing
    lines = run_report.summary_lines(out, NAMES)
    assert lines[0] == "  Bob: model says Victor, beliefs say Victor 50%"
    assert lines[1] == "  Hal: model says Victor, beliefs say no idea"


def test_after_run_saves_beliefs_in_the_sidecar_data():
    w = build_world(SC)
    extra = run_report.after_run(w, Memories(), FakeClient([{"suspect": None, "why": "x"}] * 5),
                                 {}, SC)  # fmt: skip
    assert extra["beliefs"]["confidence"]["npc_bob"]["npc_victor"] == 0.5
    assert "belief_suspect" in extra["interview"]["npc_bob"]
    json.dumps(extra)  # must be JSON safe
    # Without a scenario the old behaviour is unchanged.
    old = run_report.after_run(w, Memories(), FakeClient([{"suspect": None, "why": "x"}] * 5), {})
    assert "beliefs" not in old and "belief_suspect" not in old["interview"]["npc_bob"]


def test_compare_shows_belief_columns_and_trust_in_player(tmp_path):
    a = make_run(tmp_path, "a.db")
    b = make_run(tmp_path, "b.db", sidecar=False)  # an old-style run: no sidecar at all
    text = compare_command.compare_runs([a, b])
    assert "Beliefs (from the log):" in text
    assert "Victor 50%" in text  # Bob and Alice still lean on what they saw
    assert "Trust in the player at the end:" in text
    # Bob heard the lie against his own sighting, so he trusts the player less (0.3 - 0.15).
    assert "a.db: Alice 30%, Bob 15%" in text


def test_compare_without_replayed_beliefs_shows_dashes():
    run = {"name": "old.db", "events": [], "sidecar": {}}  # no "beliefs" key at all
    assert "Beliefs: -" in compare.format_compare([run], {})


def test_cli_trace_runs(tmp_path):
    db = make_run(tmp_path)
    res = CliRunner().invoke(cli.app, ["trace", str(db), "npc_hal"])
    assert res.exit_code == 0 and "Who believes Hal (npc_hal)" in res.output
    res = CliRunner().invoke(cli.app, ["trace", str(tmp_path / "nope.db"), "npc_hal"])
    assert res.exit_code == 1
