"""The body of `whisperwick judge`, kept out of cli.py. The client is built by the caller."""

import json
from pathlib import Path

from whisperwick import compare, eval_measures, judge_run


def judge_run_command(db: Path, client, model: str, limit: int) -> str:
    """Judge one finished run, write <db>.judge.json, return a short summary for the screen."""
    run = compare.load_run(db)
    names = compare.load_names([run])
    log = run["beliefs"]
    result = judge_run.judge(run["events"], log.records if log else [], run["sidecar"],
                             names, client, limit)  # fmt: skip
    result["model"] = model
    path = eval_measures.judge_path(db)
    path.write_text(json.dumps(result, indent=2, sort_keys=True))
    s = result["summary"]
    return "\n".join([f"Judge: {path}", json.dumps(s, indent=2, sort_keys=True)])
