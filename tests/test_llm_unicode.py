"""Broken model escapes must not poison future requests. No network calls."""

import io
import json
import urllib.request

import pytest

from whisperwick.kev_client import KevClient
from whisperwick.llm_client import LlamaServerClient, OllamaClient


@pytest.mark.parametrize("client_type", [OllamaClient, LlamaServerClient, KevClient])
def test_request_replaces_lone_surrogates(monkeypatch, client_type):
    seen = []

    def urlopen(request, timeout=None):
        seen.append(request)
        payload = {
            "message": {"content": "{}"},
            "choices": [{"message": {"content": "{}"}}],
            "answers": {},
        }
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    text = "é 😀 \ud83d\ude00 low:\udcfb high:\ud800"
    expected = "é 😀 😀 low:\ufffd high:\ufffd"
    client = client_type("http://unused/v1", "model")
    if client_type is KevClient:
        client.ask(text, {})
    else:
        client.chat([{"role": "user", "content": text}], {})

    encoded = seen[0].data
    body = json.loads(encoded.decode("utf-8"))
    actual = body["state"] if client_type is KevClient else body["messages"][0]["content"]
    assert actual == expected
    assert b"\\udcfb" not in encoded
    assert b"\\ud800" not in encoded


@pytest.mark.parametrize("client_type", [OllamaClient, LlamaServerClient])
def test_reply_cleans_all_json_strings(monkeypatch, client_type):
    # Keep the model's escapes literal so json.loads sees lone halves and a valid pair.
    content = (
        r'{"nested": [{"\udcfb": "low:\udcfb high:\ud800",'
        r'"normal": "é 😀 \ud83d\ude00"}], "other": [1, true, null]}'
    )
    payload = {
        "message": {"content": content},
        "choices": [{"message": {"content": content}}],
    }
    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda request, timeout=None: io.BytesIO(json.dumps(payload).encode()),
    )
    result = client_type("http://unused/v1", "model").chat([], {})
    assert result == {
        "nested": [{"\ufffd": "low:\ufffd high:\ufffd", "normal": "é 😀 😀"}],
        "other": [1, True, None],
    }
