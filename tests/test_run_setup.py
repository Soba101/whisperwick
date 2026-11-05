"""Setup capture never needs a model, a socket, or the caller's working directory."""

import hashlib
import json
import subprocess
import threading
import time
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

import whisperwick
from whisperwick import run_setup


def test_allowlisted_props_and_template_hash(monkeypatch):
    monkeypatch.setattr(run_setup, "git_setup", lambda: {"commit": "abc", "dirty": False})
    template = "{{ messages }}"
    sampling = dict(temperature=0.8, top_p=0.9, top_k=40, min_p=0.05,
                    seed=42, repeat_penalty=1.1)
    props = {
        "build_info": "b123-abc", "model_path": "/private/models/model.gguf",
        "total_slots": 5, "chat_template": template,
        "default_generation_settings": {"n_ctx": 8192, **sampling, "api_key": "secret"},
        "api_key": "secret", "url": "http://private-host", "hostname": "private-host",
    }
    calls = []

    def fetch(url, *, timeout):
        calls.append((url, timeout))
        return props

    setup = run_setup.collect_setup(
        "llama-server", "model", "http://private-host/v1/", real_client=True, fetch=fetch,
        temperature=0.7,
    )
    assert calls == [("http://private-host/props", 2.0)]
    assert setup == {
        "commit": "abc", "dirty": False, "llm_server": "llama-server", "model": "model",
        "temperature": 0.7,
        "server": {"build_info": "b123-abc", "model_path": "model.gguf", "total_slots": 5,
                   "n_ctx": 8192, **sampling,
                   "chat_template_sha256": hashlib.sha256(template.encode()).hexdigest()},
    }
    assert "private" not in json.dumps(setup) and template not in json.dumps(setup)


def test_nested_sampling_and_windows_model_path():
    props = {"model_path": r"C:\models\model.gguf", "n_ctx": 16384,
             "default_generation_settings": {"n_ctx": 8192, "params": {"temperature": 0.6}},
             "total_slots": {"token": "secret"}}
    assert run_setup.allowed_props(props) == {
        "model_path": "model.gguf", "n_ctx": 16384, "temperature": 0.6,
    }


@pytest.mark.parametrize(("error", "reason"), [
    (OSError("http://secret-host/?token=secret"), "fetch failed"),
    (TimeoutError("secret"), "timeout"),
    (urllib.error.URLError(TimeoutError("secret")), "timeout"),
    (urllib.error.HTTPError("http://secret-host", 401, "secret", {}, None), "HTTP 401"),
    (ValueError("secret"), "invalid props"),
    (RuntimeError("secret"), "fetch failed"),
])
def test_fetch_errors_have_no_private_details(error, reason):
    def fetch(url, *, timeout):
        raise error

    assert run_setup.server_setup("llama-server", "http://secret-host/v1", fetch) == {
        "error": reason,
    }


@pytest.mark.parametrize("payload", [None, [], {"default_generation_settings": None}])
def test_bad_payload_is_harmless(payload):
    assert run_setup.server_setup("llama-server", "unused", lambda *a, **kw: payload) == {
        "error": "invalid props",
    }


def test_probe_deadline_even_if_fetch_does_not_return(monkeypatch):
    # A blocked fetch must not delay the run beyond the shared deadline.
    monkeypatch.setattr(run_setup, "PROPS_TIMEOUT", 0.02)
    release = threading.Event()

    def fetch(*args, **kwargs):
        release.wait(1)
        return {}

    started = time.monotonic()
    try:
        assert run_setup.server_setup("llama-server", "unused", fetch) == {"error": "timeout"}
        assert time.monotonic() - started < 0.5
    finally:
        release.set()


@pytest.mark.parametrize("server", ["ollama", "other", None])
def test_other_servers_skip_probe(server):
    def fetch(*args, **kwargs):
        pytest.fail("unsupported servers must not be contacted")

    assert run_setup.server_setup(server, "unused", fetch) == {"error": "unsupported server"}


@pytest.mark.parametrize("dirty", [False, True])
def test_git_uses_package_checkout_and_ignores_untracked(monkeypatch, dirty):
    calls = []

    def git(command, **kwargs):
        calls.append(command)
        assert kwargs == dict(capture_output=True, text=True, check=True, timeout=1)
        value = "abcdef\n" if "rev-parse" in command else " M tracked.py\n" if dirty else ""
        return SimpleNamespace(stdout=value)

    monkeypatch.setattr(run_setup.subprocess, "run", git)
    assert run_setup.git_setup() == {"commit": "abcdef", "dirty": dirty}
    root = str(Path(whisperwick.__file__).resolve().parent)
    assert calls == [["git", "-C", root, "rev-parse", "HEAD"],
                     ["git", "-C", root, "status", "--porcelain", "--untracked-files=no"]]


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.CalledProcessError(1, "git"),
                                 subprocess.TimeoutExpired("git", 1)])
def test_git_failure_is_unknown(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(run_setup.subprocess, "run", fail)
    assert run_setup.git_setup() == {"commit": None, "dirty": None}


def test_stub_keeps_git_but_does_not_fetch(monkeypatch):
    monkeypatch.setattr(run_setup, "git_setup", lambda: {"commit": "abc", "dirty": True})

    def fetch(*args, **kwargs):
        pytest.fail("a stub must not probe")

    assert run_setup.collect_setup("llama-server", "model", "unused", fetch=fetch) == {
        "commit": "abc", "dirty": True, "llm_server": "llama-server", "model": "model",
        "server": {"error": "no model client"},
    }
