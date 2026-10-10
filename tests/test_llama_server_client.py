"""LlamaServerClient and the LLM_SERVER choice. No network: urlopen is faked."""

import io
import json
import urllib.error
import urllib.request

import pytest

from whisperwick import cli, settings
from whisperwick.llm_client import LlamaServerClient, LLMError, OllamaClient

SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}}
MESSAGES = [{"role": "user", "content": "hi"}]


def fake_urlopen(monkeypatch, payload=None, error=None):
    """Replace urlopen; return a dict that holds the captured request."""
    seen = {}

    def urlopen(request, timeout=None):
        seen["request"], seen["timeout"] = request, timeout
        if error:
            raise error
        return io.BytesIO(payload if isinstance(payload, bytes) else json.dumps(payload).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return seen


def reply(content):
    return {"choices": [{"message": {"content": content}}]}


def test_request_and_parsed_reply(monkeypatch):
    seen = fake_urlopen(monkeypatch, reply('{"a": "x"}'))
    client = LlamaServerClient("http://h:8080/v1/", "m1")
    assert client.chat(MESSAGES, SCHEMA) == {"a": "x"}
    assert seen["request"].full_url == "http://h:8080/v1/chat/completions"
    assert seen["timeout"] == 120
    body = json.loads(seen["request"].data)
    assert body["messages"] == MESSAGES
    assert body["model"] == "m1"
    assert body["temperature"] == 0.7
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["stream"] is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"error": urllib.error.URLError("down")},
        {"error": TimeoutError("slow")},
        {"payload": b"not json"},
        {"payload": reply("not json")},
        {"payload": {"choices": []}},
        {"payload": {"nothing": 1}},
    ],
)
def test_failures_become_llm_error(monkeypatch, kwargs):
    fake_urlopen(monkeypatch, **kwargs)
    with pytest.raises(LLMError):
        LlamaServerClient("http://h:8080/v1", "m1").chat(MESSAGES, SCHEMA)


def test_llm_server_setting(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_SERVER", raising=False)
    env = tmp_path / ".env"
    assert settings.llm_server(env) == "ollama"
    env.write_text("LLM_SERVER=llama-server\n")
    assert settings.llm_server(env) == "llama-server"
    env.write_text("LLM_SERVER=vllm\n")
    with pytest.raises(ValueError, match="LLM_SERVER"):
        settings.llm_server(env)


def test_make_client_picks_class():
    assert isinstance(cli.make_client("ollama", "http://h/v1", "m"), OllamaClient)
    assert isinstance(cli.make_client("llama-server", "http://h/v1", "m"), LlamaServerClient)
