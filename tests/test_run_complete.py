# The run-complete script must reject every kind of unfinished run.
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "run-complete.py"


def check(path, days=3):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(path), str(days)], capture_output=True, text=True
    )


def write(tmp_path, data):
    p = tmp_path / "run.json"
    p.write_text(json.dumps(data))
    return p


def test_complete(tmp_path):
    r = check(write(tmp_path, {"minutes": 4320, "stats": {}}))
    assert r.returncode == 0 and r.stdout == ""


def test_stopped(tmp_path):
    r = check(write(tmp_path, {"minutes": 4320, "stats": {"stopped": "20 errors"}}))
    assert r.returncode == 1 and "stopped" in r.stdout


def test_short_minutes(tmp_path):
    r = check(write(tmp_path, {"minutes": 100, "stats": {}}))
    assert r.returncode == 1 and "100" in r.stdout


def test_missing_file(tmp_path):
    assert check(tmp_path / "nope.json").returncode == 1


def test_bad_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{oops")
    assert check(p).returncode == 1
