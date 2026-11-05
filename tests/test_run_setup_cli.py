"""Setup stays in sidecars and is captured before the first model call."""

import json

import pytest
from helpers import SCENARIO
from test_llm_sim import LookClient
from typer.testing import CliRunner

from whisperwick import cli, llm_cli, llm_run, run_setup
from whisperwick.llm_client import LlamaServerClient
from whisperwick.memory import Memories
from whisperwick.scenario import load_scenario


def test_sidecar_setup_is_optional_and_round_trips(tmp_path):
    args = (SCENARIO, "model", 1, {}, {}, Memories())
    assert "setup" not in llm_run.sidecar_data(*args)
    setup = {"commit": "abc", "dirty": False, "server": {"error": "no model client"}}
    path = tmp_path / "run.json"
    llm_run.write_sidecar(path, llm_run.sidecar_data(*args, setup=setup))
    assert json.loads(path.read_text())["setup"] == setup


@pytest.mark.parametrize("real_client", [False, True])
def test_cli_captures_once_before_calls(monkeypatch, tmp_path, real_client):
    look = LookClient()
    client = LlamaServerClient("unused/v1", "model") if real_client else look
    probes, calls = [], []

    def fetch(url, *, timeout):
        assert not calls
        probes.append(url)
        return {"build_info": "b123"}

    def chat(messages, schema, **kwargs):
        if real_client:
            assert probes == ["http://private-host/props"]
        calls.append(schema)
        return LookClient.chat(look, messages, schema)

    client.chat = chat
    monkeypatch.setattr(run_setup, "fetch_props", fetch)
    captures = []

    def git():
        assert not calls
        captures.append(True)
        return {"commit": "abc", "dirty": False}

    monkeypatch.setattr(run_setup, "git_setup", git)
    monkeypatch.setattr(llm_cli, "llm_settings", lambda: ("http://private-host/v1", "model"))
    monkeypatch.setattr(llm_cli, "make_client", lambda *args: client)
    monkeypatch.setattr(llm_cli.settings, "llm_server", lambda: "llama-server")
    monkeypatch.setattr(llm_cli.settings, "llm_temperature", lambda: 1.0)
    monkeypatch.setattr(llm_cli.settings, "parallel", lambda: 1)
    monkeypatch.setattr(llm_cli.settings, "llm_slots", lambda: None)
    monkeypatch.setattr(llm_cli.settings, "group_turns", lambda: False)
    monkeypatch.setattr(llm_cli.run_report, "after_run", lambda *args: {"interview": {}})
    monkeypatch.setattr(llm_cli.run_report, "summary_lines", lambda *args: [])
    db = str(tmp_path / "run.db")
    llm_cli.run_with_llm(load_scenario(SCENARIO), SCENARIO, db, 42, 1)
    setup = json.loads(llm_run.sidecar_path(db).read_text())["setup"]
    assert captures == [True] and calls
    assert setup["commit"] == "abc" and setup["dirty"] is False
    assert setup["llm_server"] == "llama-server" and setup["model"] == "model"
    assert setup["temperature"] == 1.0
    assert setup["server"] == ({"build_info": "b123"} if real_client
                               else {"error": "no model client"})
    assert len(probes) == int(real_client)


def test_saved_stub_has_setup_and_unchanged_events(monkeypatch, tmp_path):
    def fetch(*args, **kwargs):
        pytest.fail("a stub must not contact a model server")

    monkeypatch.setattr(run_setup, "fetch_props", fetch)
    monkeypatch.setattr(run_setup, "git_setup", lambda: {"commit": "abc", "dirty": True})
    db = tmp_path / "stub.db"
    result = CliRunner().invoke(cli.app, ["run", "--hours", "1", "--db", str(db)])
    memory = CliRunner().invoke(cli.app, ["run", "--hours", "1"])
    assert result.exit_code == memory.exit_code == 0
    assert result.output == memory.output
    setup = json.loads(llm_run.sidecar_path(db).read_text())["setup"]
    assert setup == {"commit": "abc", "dirty": True, "llm_server": None, "model": None,
                     "server": {"error": "no model client"}}
