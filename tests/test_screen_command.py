"""The screen command writes reusable lists and results without a server in tests."""

import json

from test_llm_sim import LookClient
from test_screen_replay import source_fixture  # noqa: F401 (shared fixture)
from typer.testing import CliRunner

from whisperwick import llm_cli, llm_run, settings
from whisperwick.cli import app
from whisperwick.screen_results import run_picked
from whisperwick.screen_turns import pick

runner = CliRunner()


def test_check_pick_run_and_table(saved_run, tmp_path, monkeypatch):
    db = saved_run()
    turns, results = tmp_path / "turns.json", tmp_path / "results.json"
    checked = runner.invoke(app, ["screen", "check", str(db)])
    assert checked.exit_code == 0 and ": ok; unused recalls=" in checked.stdout
    picked = runner.invoke(app, ["screen", "pick", str(db), "--acts", "2", "--thinks", "1",
                                 "--seed", "8", "--out", str(turns)])
    assert picked.exit_code == 0
    calls = []

    def make(server, url, model):
        calls.append((server, url, model))
        return LookClient()

    monkeypatch.setattr(llm_cli, "make_client", make)
    monkeypatch.setattr(settings, "llm_server", lambda: "test-server")
    ran = runner.invoke(app, ["screen", "run", str(turns), "--out", str(results),
                              "--base-url", "http://example.invalid", "--model", "candidate"])
    assert ran.exit_code == 0, ran.output
    assert calls == [("test-server", "http://example.invalid", "candidate")]
    data = json.loads(results.read_text())
    assert data["totals"]["turns"] == 3 and data["totals"]["minutes"] >= 0
    table = runner.invoke(app, ["screen", "table", str(results)])
    assert table.exit_code == 0 and "rejected_share" in table.stdout


def test_drift_stops_before_requests(saved_run):
    db = saved_run()
    picked = pick([db], 2, 1)
    sidecar = llm_run.sidecar_path(db)
    data = json.loads(sidecar.read_text())
    data["notebooks"]["npc_alice"]["me"] = "changed"
    sidecar.write_text(json.dumps(data))

    class NoCalls:
        def chat(self, messages, schema):
            raise AssertionError("source drift must stop before any candidate request")

    try:
        run_picked(picked, NoCalls())
    except ValueError as exc:
        assert "notebooks" in str(exc)
    else:
        raise AssertionError("source drift was missed")
