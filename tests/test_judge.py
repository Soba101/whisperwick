"""`whisperwick judge`: sampling, questions, summary, failures. A fake judge, no network."""

import json
from pathlib import Path

from eval_helpers import make_run, record
from typer.testing import CliRunner

from whisperwick import cli, compare, eval_measures, judge_run, llm_cli
from whisperwick.llm_client import LLMError


class FakeJudge:
    """Answers by schema: yes, score 4, no misread. Records every call. Can fail on demand."""

    def __init__(self, fail_on=()):
        self.calls, self.fail_on = [], fail_on

    def chat(self, messages, schema):
        self.calls.append(messages)
        props = schema["properties"]
        if any(key in messages[1]["content"] for key in self.fail_on):
            raise LLMError("down")
        if "answer" in props:
            return {"answer": "yes"}
        if "misread" in props:
            return {"misread": True, "what": "calls Bob dead"}
        return {"score": 4}


def patch_cli(monkeypatch, client):
    monkeypatch.setattr(llm_cli.settings, "llm_base_url", lambda: "http://x")
    monkeypatch.setattr(llm_cli.settings, "llm_model", lambda: "m")
    monkeypatch.setattr(llm_cli.settings, "llm_server", lambda: "ollama")
    seen = []

    def make_client(server, url, model, temperature=0.7):
        seen.append(temperature)
        return client

    monkeypatch.setattr(llm_cli, "make_client", make_client)
    return seen


def test_pick_is_even_and_deterministic():
    assert judge_run.pick(list(range(10)), 20) == list(range(10))
    assert judge_run.pick(list(range(10)), 5) == [0, 2, 4, 6, 8]
    assert judge_run.pick(list(range(10)), 0) == []


def test_judge_writes_items_and_summary(tmp_path, monkeypatch):
    db = make_run(tmp_path)
    client = FakeJudge()
    seen = patch_cli(monkeypatch, client)
    out = CliRunner().invoke(cli.app, ["judge", db, "--limit", "5"])
    assert out.exit_code == 0, out.output
    assert seen == [0.0]  # the judge asks for temperature 0
    result = json.loads(eval_measures.judge_path(Path(db)).read_text())
    s = result["summary"]
    assert s["claim_agreement"] == 1.0 and s["support_mean"] == 4 and s["support_ok"] == 1.0
    assert s["misread_rate"] == 1.0 and s["coherence_by_day"] == {"1": 4}
    # Two talks with claims, one cited suspect thought, one cited thought, one day.
    assert s["asked"] == {"claims": 2, "support": 1, "misreads": 1, "coherence": 1}
    # Every item keeps what the judge was shown, so a person can spot-check it.
    item = result["items"]["claims"][0]
    assert "Bob said to Victor" in item["inputs"] and item["answer"] == {"answer": "yes"}
    # The judge never sees the secret.
    assert not any("murderer" in m[1]["content"] for m in client.calls)


def test_limit_caps_each_question_type(tmp_path):
    db = make_run(tmp_path)
    result = judge_run.judge(*inputs(db), FakeJudge(), limit=1)
    assert result["summary"]["asked"]["claims"] == 1


def inputs(db):
    run = compare.load_run(Path(db))
    return run["events"], run["beliefs"].records, run["sidecar"], compare.load_names([run])


def test_model_failures_are_counted_not_raised(tmp_path):
    db = make_run(tmp_path, records=[record("npc_alice", "npc_victor", ["wet boots"])])
    result = judge_run.judge(*inputs(db), FakeJudge(fail_on=("really",)))
    s = result["summary"]
    assert s["failures"]["claims"] == 2 and s["claim_agreement"] is None
    assert s["support_mean"] == 4  # the other questions still ran


def test_bad_reply_shape_counts_as_a_failure(tmp_path):
    class Odd:
        def chat(self, messages, schema):
            return {"score": 9, "answer": "maybe", "misread": "yes"}

    db = make_run(tmp_path)
    s = judge_run.judge(*inputs(db), Odd())["summary"]
    assert sum(s["failures"].values()) == sum(s["asked"].values()) > 0


def test_eval_shows_judge_numbers_when_a_judge_file_exists(tmp_path, monkeypatch):
    db = make_run(tmp_path)
    patch_cli(monkeypatch, FakeJudge())
    CliRunner().invoke(cli.app, ["judge", db])
    out = CliRunner().invoke(cli.app, ["eval", db])
    assert "Judge (from <db>.judge.json)" in out.output and "4.00" in out.output
