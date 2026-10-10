"""Talks to a local Ollama server. Standard library only, no extra packages.

The client knows nothing about the game. It sends messages and a JSON schema,
and gives back the parsed JSON reply.
"""

import json
import urllib.error
import urllib.request


class LLMError(Exception):
    """The model server failed, or its reply was not usable JSON."""


def chat_url(base_url: str) -> str:
    """Build the native chat URL. The .env holds an OpenAI-style URL ending in /v1."""
    base = base_url.rstrip("/").removesuffix("/v1")
    return f"{base}/api/chat"


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        keep_alive: str = "30m",
        timeout: int = 120,
        temperature: float = 0.7,  # runs use 0.7, the after-run judge uses 0
    ):
        self.url = chat_url(base_url)
        self.temperature = temperature
        self.model = model
        self.keep_alive = keep_alive  # keeps the model loaded between turns
        self.timeout = timeout

    def chat(self, messages: list[dict], schema: dict) -> dict:
        body = {
            "model": self.model,
            "messages": messages,
            "format": schema,  # the server forces the reply to match this schema
            "think": False,  # no hidden reasoning: it only costs time here
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": self.temperature},
        }
        request = urllib.request.Request(
            self.url, json.dumps(body).encode(), {"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                reply = json.load(response)
            return json.loads(reply["message"]["content"])
        except (OSError, ValueError, KeyError, TypeError) as e:
            # OSError covers URLError, HTTPError and timeouts. ValueError covers bad JSON.
            raise LLMError(f"chat failed: {e}") from e


def completions_url(base_url: str) -> str:
    """Build the OpenAI-style chat URL. The base already ends in /v1."""
    return f"{base_url.rstrip('/')}/chat/completions"


class LlamaServerClient:
    """Talks to llama.cpp's llama-server, which allows several calls at once.

    Ollama refuses parallel requests for our model, llama-server does not.
    Nothing is kept between calls, so many threads can share one client.
    """

    def __init__(self, base_url: str, model: str, timeout: int = 120, temperature: float = 0.7):
        self.url = completions_url(base_url)
        self.temperature = temperature
        self.model = model  # llama-server ignores it, other OpenAI-style servers use it
        self.timeout = timeout

    def chat(self, messages: list[dict], schema: dict) -> dict:
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            # The server forces the reply to match this schema.
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "reply", "schema": schema},
            },
            "chat_template_kwargs": {"enable_thinking": False},  # no hidden reasoning
            "stream": False,
        }
        request = urllib.request.Request(
            self.url, json.dumps(body).encode(), {"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                reply = json.load(response)
            return json.loads(reply["choices"][0]["message"]["content"])
        except (OSError, ValueError, KeyError, IndexError, TypeError) as e:
            # Same catch as OllamaClient, plus IndexError for an empty choices list.
            raise LLMError(f"chat failed: {e}") from e


class FakeClient:
    """A stand-in for tests. Returns queued replies in order and records every call."""

    def __init__(self, replies: list[dict]):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def chat(self, messages: list[dict], schema: dict) -> dict:
        self.calls.append({"messages": messages, "schema": schema})
        if not self.replies:
            raise LLMError("no queued reply")
        return self.replies.pop(0)
