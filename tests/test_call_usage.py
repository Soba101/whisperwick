"""Call logging: the recorder, the clients' use of it, the sidecar and the eval table."""

import io
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from eval_helpers import make_run

from whisperwick import eval_command, llm_run
from whisperwick.call_usage import UsageRecorder
from whisperwick.llm_client import LlamaServerClient, LLMError, OllamaClient

MESSAGES = [{"role": "user", "content": "hi"}]


def test_recorder_mixed_calls_and_p90():
    r = UsageRecorder()
    for i in range(1, 11):  # latencies 1..10
        r.record(float(i), prompt=10, output=2)
    r.record(0.5, "HTTP 400")
    r.record(0.5, "HTTP 400")
    r.record(0.5, "timeout")
    s = r.summary()
    assert (s["requests"], s["errors"]) == (13, 3)
    assert s["error_reasons"] == {"HTTP 400": 2, "timeout": 1}
    assert s["prompt_tokens"] == 100 and s["output_tokens"] == 20
    assert s["latency_p90_s"] == 9.0  # nearest rank: ceil(0.9 * 13) = 12th of 13
    assert json.dumps(s)


def test_recorder_missing_data_is_none():
    s = UsageRecorder().summary()
    assert s["requests"] == 0 and s["latency_p90_s"] is None and s["prompt_tokens"] is None
    r = UsageRecorder()
    r.record(1.0)
    assert r.summary()["output_tokens"] is None
    assert r.summary()["ms_per_output_token_mean"] is None


def test_recorder_threads():
    r = UsageRecorder()

    def work():
        for _ in range(200):
            r.record(0.1, output=1)

    threads = [threading.Thread(target=work) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert r.summary()["requests"] == 800 and r.summary()["output_tokens"] == 800


def fake(monkeypatch, payload=None, error=None):
    def urlopen(request, timeout=None):
        if error:
            raise error
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


def test_llama_server_usage(monkeypatch):
    fake(monkeypatch, {
        "choices": [{"message": {"content": "{}"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20,
                  "prompt_tokens_details": {"cached_tokens": 80}},
        "timings": {"prompt_ms": 50.0, "predicted_n": 20, "predicted_ms": 400.0},
    })  # fmt: skip
    c = LlamaServerClient("http://h/v1", "m")
    c.chat(MESSAGES, {})
    s = c.usage.summary()
    assert (s["prompt_tokens"], s["output_tokens"], s["cached_tokens"]) == (100, 20, 80)
    assert s["prompt_ms_mean"] == 50.0 and s["ms_per_output_token_mean"] == 20.0


def test_ollama_usage(monkeypatch):
    fake(monkeypatch, {"message": {"content": "{}"}, "prompt_eval_count": 7, "eval_count": 3})
    c = OllamaClient("http://h/v1", "m")
    c.chat(MESSAGES, {})
    s = c.usage.summary()
    assert (s["prompt_tokens"], s["output_tokens"], s["cached_tokens"]) == (7, 3, None)


def test_http_error_keeps_status_and_body(monkeypatch):
    err = urllib.error.HTTPError("u", 400, "Bad", {}, io.BytesIO(b"context too long"))
    fake(monkeypatch, error=err)
    c = LlamaServerClient("http://h/v1", "m")
    with pytest.raises(LLMError, match="HTTP 400: context too long"):
        c.chat(MESSAGES, {})
    s = c.usage.summary()
    assert s["errors"] == 1 and s["error_reasons"] == {"HTTP 400": 1}


@pytest.mark.parametrize("error,reason", [
    (TimeoutError("slow"), "timeout"),
    (urllib.error.URLError("down"), "connection"),
])  # fmt: skip
def test_other_failure_reasons(monkeypatch, error, reason):
    fake(monkeypatch, error=error)
    c = OllamaClient("http://h/v1", "m")
    with pytest.raises(LLMError):
        c.chat(MESSAGES, {})
    assert c.usage.summary()["error_reasons"] == {reason: 1}


def test_bad_json_reason(monkeypatch):
    fake(monkeypatch, {"choices": [{"message": {"content": "nope"}}]})
    c = LlamaServerClient("http://h/v1", "m")
    with pytest.raises(LLMError):
        c.chat(MESSAGES, {})
    assert c.usage.summary()["error_reasons"] == {"bad JSON": 1}


def test_sidecar_has_usage_only_with_a_recorder():
    r = UsageRecorder()
    r.record(1.0, output=5)

    class Client:
        usage = r

    with_usage = llm_run.sidecar_data("s", "m", 1, {}, {}, {}, client=Client())
    assert with_usage["usage"]["requests"] == 1
    assert "usage" not in llm_run.sidecar_data("s", "m", 1, {}, {}, {})


def test_eval_calls_table_with_and_without_usage(tmp_path):
    db = make_run(tmp_path, "new")
    path = llm_run.sidecar_path(db)
    data = json.loads(path.read_text())
    data["usage"] = {"requests": 10, "errors": 1, "output_tokens": 250, "latency_p90_s": 4.26}
    data["stats"]["turn_reasons"] = {"answer": 8, "woken": 3, "first": 5, "routine": 2}
    path.write_text(json.dumps(data))
    old = make_run(tmp_path, "old")
    old_path = llm_run.sidecar_path(old)
    old_data = json.loads(old_path.read_text())
    old_data["stats"].pop("turn_reasons")
    old_path.write_text(json.dumps(old_data))
    text = eval_command.eval_runs([Path(db), Path(old)])
    block = text.split("Calls (")[1].split("\n\n")[0]
    new_row = next(line for line in block.splitlines() if line.startswith("new.db"))
    old_row = next(line for line in block.splitlines() if line.startswith("old.db"))
    assert "Turns a/w/f/r" in block
    assert new_row.split() == ["new.db", "10", "1", "25", "4.3", "8/3/5/2"]
    assert old_row.split() == ["old.db", "-", "-", "-", "-", "-"]
