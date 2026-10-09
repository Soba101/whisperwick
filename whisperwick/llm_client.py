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
    def __init__(self, base_url: str, model: str, keep_alive: str = "30m", timeout: int = 120):
        self.url = chat_url(base_url)
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
            "options": {"temperature": 0.7},
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
