"""CLI and sidecar tests for LLM runs. No model server is ever contacted."""

import json

from helpers import SCENARIO
from typer.testing import CliRunner

from whisperwick import cli, llm_run
from whisperwick.memory import Memories
from whisperwick.scenario import load_scenario


def test_llm_run_without_settings_points_at_env_example(monkeypatch, tmp_path):
    # Stub out the settings so no real .env file or environment is read.
    monkeypatch.setattr(cli.settings, "llm_base_url", lambda: None)
    monkeypatch.setattr(cli.settings, "llm_model", lambda: None)
    db = tmp_path / "x.db"
    result = CliRunner().invoke(cli.app, ["run", "--agent", "llm", "--db", str(db)])
    assert result.exit_code == 1
    assert ".env.example" in result.output
    assert not db.exists()  # a bad setup leaves nothing behind


def test_stub_run_still_works_with_days():
    result = CliRunner().invoke(cli.app, ["run", "--days", "1"])
    assert result.exit_code == 0 and "events." in result.output


def test_sidecar_has_expected_keys_and_content(tmp_path):
    memories = Memories()
    for i in range(7):
        memories["npc_hal"].add(i, f"memory {i}", 1)
    memories["npc_hal"].add(1320, "Victor did it.", 8, "reflection")
    secrets = load_scenario(SCENARIO).secrets
    data = llm_run.sidecar_data(SCENARIO, "m1", 60, {"calls": 3}, secrets, memories)
    path = llm_run.sidecar_path(tmp_path / "run.db")
    llm_run.write_sidecar(path, data)

    saved = json.loads(path.read_text())
    assert path.name == "run.json"
    assert set(saved) == {
        "scenario", "model", "minutes", "stats", "secrets", "reflections", "final_memories"
    }  # fmt: skip
    assert saved["reflections"]["npc_hal"] == [{"tick": 1320, "text": "Victor did it."}]
    # Only the last five memories are kept.
    assert len(saved["final_memories"]["npc_hal"]) == 5


def test_default_db_path_and_rejection_rate():
    assert llm_run.default_db_path("murder").startswith("data/run-murder-")
    assert llm_run.rejection_rate({}) == 0.0
    assert llm_run.rejection_rate({"calls": 4, "rejected": 1}) == 0.25
