"""The body of `whisperwick judge`, kept out of cli.py. The client is built by the caller."""

import json
from pathlib import Path

from whisperwick import compare, eval_measures
from whisperwick.kev_client import MODEL
from whisperwick.llm_client import LLMError


def judge_run_command(db: Path, client, model: str, judge, limit: int) -> str:
    """Judge one finished run, write <db>.judge.json, return a short summary for the screen."""
    run = compare.load_run(db)
    names = compare.load_names([run])
    log = run["beliefs"]
    # `judge` is the chat judge or the Kev judge; both give the same file shape.
    result = judge(run["events"], log.records if log else [], run["sidecar"],
                   names, client, limit)  # fmt: skip
    result["model"] = model
    path = eval_measures.judge_path(db)
    path.write_text(json.dumps(result, indent=2, sort_keys=True))
    s = result["summary"]
    return "\n".join([f"Judge: {path} (judge: {model})", json.dumps(s, indent=2, sort_keys=True)])


def check_kev(client) -> str:
    """A tiny connectivity check: can we list Kev's models?"""
    try:
        listing = client.models()
    except LLMError as e:
        return f"Kev check failed: {e}"
    return "Kev OK" if MODEL in json.dumps(listing) else f"Kev answered, but {MODEL} is not listed"
