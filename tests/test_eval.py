"""`whisperwick eval`: code-only measures and the summary. No model, no network."""

import json
from pathlib import Path

from eval_helpers import make_run, strip_week6
from typer.testing import CliRunner

from whisperwick import cli, eval_measures, llm_run
from whisperwick.compare import load_run


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
