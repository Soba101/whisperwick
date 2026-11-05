"""Compare full setups while keeping old runs readable."""

import copy
import json

import pytest
from typer.testing import CliRunner

from whisperwick import cli, compare
from whisperwick.events import EventLog

SETUP = {
    "commit": "0123456789abcdef", "dirty": False, "llm_server": "llama-server", "model": "m",
    "server": {"build_info": "b123", "total_slots": 5, "n_ctx": 8192, "temperature": 0.7,
               "chat_template_sha256": "abcdef0123456789"},
}


def run(name, setup=None):
    return {"name": name, "events": [], "sidecar": {"setup": setup} if setup else {}}


def test_equal_setups_and_old_runs_do_not_warn():
    out = compare.format_compare([run("a", SETUP), run("b", copy.deepcopy(SETUP)), run("old")], {})
    assert "commit 01234567, build b123, slots 5, n_ctx 8192, temperature 0.7" in out
    assert "template abcdef01" in out
    assert "old: -" in out and "WARNING" not in out
    assert "WARNING" not in compare.format_compare([run("a"), run("b")], {})
    assert "WARNING" not in compare.format_compare([run("a", SETUP), run("old")], {})


@pytest.mark.parametrize("key", ["commit", "dirty", "llm_server", "model", "build_info",
                                 "total_slots", "n_ctx", "temperature", "chat_template_sha256"])
def test_each_setup_difference_warns(key):
    changed = copy.deepcopy(SETUP)
    if key in changed:
        changed[key] = True if key == "dirty" else "different"
    else:
        changed["server"][key] = "different"
    out = compare.format_compare([run("a", SETUP), run("b", changed), run("old")], {})
    assert "WARNING: Run setups differ" in out and "pooling results" in out


def test_full_hashes_are_compared_and_effective_temperature_is_shown():
    changed = copy.deepcopy(SETUP)
    changed["commit"] = SETUP["commit"] + "f"
    changed["temperature"] = 1.0
    changed["dirty"] = True
    out = compare.format_compare([run("a", SETUP), run("b", changed)], {})
    assert "commit 01234567+dirty" in out and "temperature 1.0" in out
    assert "WARNING" in out
    changed.pop("temperature")
    changed["dirty"] = False
    assert "WARNING" in compare.format_compare([run("a", SETUP), run("b", changed)], {})


def test_compare_command_loads_old_sidecar(tmp_path):
    dbs = [tmp_path / "old.db", tmp_path / "new.db"]
    for db in dbs:
        EventLog(str(db)).db.close()
    dbs[0].with_suffix(".json").write_text(json.dumps({"model": "old"}))
    dbs[1].with_suffix(".json").write_text(json.dumps({"setup": SETUP}))
    result = CliRunner().invoke(cli.app, ["compare", *(str(db) for db in dbs)])
    assert result.exit_code == 0
    assert "old.db: -" in result.output and "build b123" in result.output
    assert "WARNING" not in result.output
