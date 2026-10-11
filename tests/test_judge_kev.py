"""The Kev judge: request shape, parsing, errors, summary and settings. No network."""

import io
import json
import urllib.error
from pathlib import Path

import pytest
from eval_helpers import make_run, record
from typer.testing import CliRunner

from whisperwick import cli, compare, eval_measures, judge_kev, kev_client, llm_cli, settings
from whisperwick.kev_client import KevClient
from whisperwick.llm_client import LLMError


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(monkeypatch, reply=None, error=None):
    seen = []

    def urlopen(request, timeout=None):
        seen.append(request)
        if error:
            raise error
        return FakeResponse(json.dumps(reply).encode())

    monkeypatch.setattr(kev_client.urllib.request, "urlopen", urlopen)
    return seen


def test_request_shape_and_bearer_header(monkeypatch):
    seen = fake_urlopen(monkeypatch, {"answers": {"a": {"type": "noul", "noul": 0.9}}})
    qs = {"a": {"type": "noul", "instructions": "ok?"}}
    answers = KevClient("http://k:1/", "secret").ask("text", qs)
    assert answers == {"a": {"type": "noul", "noul": 0.9}}
    req = seen[0]
    assert req.full_url == "http://k:1/v1/systemone"
    assert json.loads(req.data) == {"state": "text", "model": "kev-latest", "questions": qs}
    assert req.get_header("Authorization") == "Bearer secret"
    KevClient("http://k:1").ask("text", qs)
    assert seen[1].get_header("Authorization") is None


@pytest.mark.parametrize("failure", [
    {"error": urllib.error.URLError("down")},
    {"error": urllib.error.HTTPError("u", 422, "too long", {}, None)},
    {"reply": ["not", "a", "dict"]},
    {"reply": {"no": "answers"}},
])
def test_client_errors_become_llm_error(monkeypatch, failure):
    fake_urlopen(monkeypatch, **failure)
    with pytest.raises(LLMError):
        KevClient("http://k").ask("t", {})


def test_models_check(monkeypatch):
    seen = fake_urlopen(monkeypatch, {"data": [{"id": "kev-latest"}]})
    assert "kev-latest" in json.dumps(KevClient("http://k").models())
    assert seen[0].full_url == "http://k/v1/models"


class FakeKev:
    """Answers every question by type. Records requests. Can fail on demand."""

    def __init__(self, fail_on=(), p=0.9, score=1.44):
        self.calls, self.fail_on, self.p, self.score = [], fail_on, p, score

    def ask(self, state, questions):
        self.calls.append((state, questions))
        if any(k in state for k in self.fail_on):
            raise LLMError("down")
        out = {}
        for key, ques in questions.items():
            if ques["type"] == "noul":
                out[key] = {"type": "noul", "noul": self.p}
            else:
                out[key] = {"type": "score", "score": self.score, "probabilities": {"1": 0.6}}
        return out


def inputs(db):
    run = compare.load_run(Path(db))
    return run["events"], run["beliefs"].records, run["sidecar"], compare.load_names([run])


def test_kev_judge_summary_and_question_shapes(tmp_path):
    db = make_run(tmp_path)
    client = FakeKev()
    result = judge_kev.judge(*inputs(db), client)
    s = result["summary"]
    assert result["judge"] == "kev-latest"
    assert s["claim_agreement"] == 1.0 and s["misread_rate"] == 1.0
    assert s["support_mean"] == pytest.approx(2.44)  # expected level 1.44, counted from 1
    assert s["support_ok"] == 0.0 and s["coherence_by_day"] == {1: pytest.approx(2.44)}
    assert s["asked"] == {"claims": 2, "support": 1, "misreads": 1, "coherence": 1}
    assert s["failures"] == {"claims": 0, "support": 0, "misreads": 0, "coherence": 0}
    # Probabilities are kept on the item.
    assert result["items"]["support"][0]["answer"]["probabilities"] == {"1": 0.6}
    # One request per thought carries both questions.
    thought = [qs for _, qs in client.calls if "support" in qs]
    assert len(thought) == 1 and set(thought[0]) == {"support", "misread"}
    assert thought[0]["support"]["type"] == "score" and len(thought[0]["support"]["criteria"]) == 5
    assert thought[0]["misread"]["type"] == "noul"
    assert not any("murderer" in state for state, _ in client.calls)


def test_misread_only_thought_has_no_support_question(tmp_path):
    db = make_run(tmp_path, records=[record("npc_bob", None, ["Alice looked around."])])
    client = FakeKev()
    s = judge_kev.judge(*inputs(db), client)["summary"]
    assert s["asked"]["support"] == 0 and s["asked"]["misreads"] == 1
    assert [set(qs) for _, qs in client.calls if "villager" in _] == [{"misread"}]


def test_low_probability_means_no(tmp_path):
    db = make_run(tmp_path)
    s = judge_kev.judge(*inputs(db), FakeKev(p=0.2))["summary"]
    assert s["claim_agreement"] == 0.0 and s["misread_rate"] == 0.0


def test_kev_failures_are_counted_not_raised(tmp_path):
    db = make_run(tmp_path)
    s = judge_kev.judge(*inputs(db), FakeKev(fail_on=("said to",)))["summary"]
    assert s["failures"]["claims"] == 2 and s["claim_agreement"] is None
    assert s["support_mean"] is not None  # the other questions still ran


def test_out_of_range_answers_are_failures(tmp_path):
    db = make_run(tmp_path)
    s = judge_kev.judge(*inputs(db), FakeKev(p=7, score=9))["summary"]
    assert sum(s["failures"].values()) == sum(s["asked"].values()) > 0


def test_cli_uses_kev_and_writes_file(tmp_path, monkeypatch):
    db = make_run(tmp_path)
    monkeypatch.setattr(llm_cli.settings, "judge_server", lambda: "kev")
    monkeypatch.setattr(llm_cli.settings, "kev_url", lambda: "http://k")
    monkeypatch.setattr(llm_cli.settings, "kev_api_key", lambda: None)
    monkeypatch.setattr(llm_cli, "KevClient", lambda url, key: FakeKev())
    out = CliRunner().invoke(cli.app, ["judge", db])
    assert out.exit_code == 0 and "kev-latest" in out.output, out.output
    result = json.loads(eval_measures.judge_path(Path(db)).read_text())
    assert result["judge"] == "kev-latest" and result["model"] == "kev-latest"


def test_cli_check(monkeypatch):
    monkeypatch.setattr(llm_cli.settings, "judge_server", lambda: "kev")
    monkeypatch.setattr(llm_cli.settings, "kev_url", lambda: "http://k")
    monkeypatch.setattr(llm_cli.settings, "kev_api_key", lambda: None)
    fake = type("C", (), {"models": lambda self: {"data": [{"id": "kev-latest"}]}})()
    monkeypatch.setattr(llm_cli, "KevClient", lambda url, key: fake)
    out = CliRunner().invoke(cli.app, ["judge", "--check"])
    assert out.exit_code == 0 and "Kev OK" in out.output


def test_settings(tmp_path):
    env = tmp_path / ".env"
    env.write_text("JUDGE_SERVER=kev\n")
    assert settings.judge_server(env) == "kev"
    with pytest.raises(ValueError, match="KEV_URL"):
        settings.kev_url(env)
    env.write_text("JUDGE_SERVER=bogus\nKEV_URL=http://k:8009\nKEV_API_KEY=abc\n")
    with pytest.raises(ValueError, match="JUDGE_SERVER"):
        settings.judge_server(env)
    assert settings.kev_url(env) == "http://k:8009" and settings.kev_api_key(env) == "abc"
    assert settings.judge_server(tmp_path / "none") == "same"


def test_long_text_splits_at_lines_under_the_size():
    # A long day is judged in parts; every part fits, and nothing is lost.
    from whisperwick.judge_kev import parts

    text = "".join(f"line {i:03d} xxxxxxxxxx\n" for i in range(100))
    pieces = parts(text, 100)
    assert all(len(p) <= 100 for p in pieces)
    assert "".join(pieces) == text
    assert all(p.endswith("\n") for p in pieces)
