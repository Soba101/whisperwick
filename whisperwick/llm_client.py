"""Talks to a local Ollama server. Standard library only, no extra packages.

The client knows nothing about the game. It sends messages and a JSON schema,
and gives back the parsed JSON reply.
"""

import json
import time
import urllib.error
import urllib.request

from whisperwick.call_usage import UsageRecorder, llama_numbers, ollama_numbers


class LLMError(Exception):
    """The model server failed, or its reply was not usable JSON.

    reason is a short, stable label ("HTTP 400", "timeout", ...) so runs can count them.
    """

    def __init__(self, message: str, reason: str = "error"):
        super().__init__(message)
        self.reason = reason


def clean_json(value):
    """Replace lone surrogates in JSON strings, including object keys."""
    if isinstance(value, str):
        # 2026-10-15: broken model escapes poisoned memories and caused HTTP 400s.
        # UTF-16 preserves valid pairs and replaces each lone half with U+FFFD.
        return value.encode("utf-16-le", errors="surrogatepass").decode(
            "utf-16-le", errors="replace"
        )
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    if isinstance(value, dict):
        return {clean_json(key): clean_json(item) for key, item in value.items()}
    return value


def encode_body(body: dict) -> bytes:
    # 2026-10-15: old memories may still contain lone surrogates rejected by llama-server.
    return json.dumps(clean_json(body), ensure_ascii=False).encode("utf-8")


def send(request, timeout: int, usage: UsageRecorder, numbers, content):
    """Do one HTTP call, time it, record it (even when it fails), return the parsed reply.

    numbers(reply) reads the token counts; content(reply) digs out the model's JSON text.
    """
    start = time.monotonic()
    nums: dict = {}
    reason = None
    try:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                reply = json.load(response)
            nums = numbers(reply)  # kept even if the content below is unusable
            return clean_json(json.loads(content(reply)))
        except urllib.error.HTTPError as e:
            # The body usually says why the server refused. It used to be lost.
            reason = f"HTTP {e.code}"
            body = e.read()[:200].decode(errors="replace")
            raise LLMError(f"chat failed: {reason}: {body}", reason) from e
        except (OSError, ValueError, KeyError, IndexError, TypeError) as e:
            # OSError covers URLError and timeouts. ValueError covers bad JSON.
            timed_out = isinstance(e, TimeoutError) or isinstance(
                getattr(e, "reason", None), TimeoutError
            )
            reason = (
                "timeout" if timed_out else "connection" if isinstance(e, OSError)
                else "bad JSON" if isinstance(e, ValueError) else "bad reply"
            )  # fmt: skip
            raise LLMError(f"chat failed: {e}", reason) from e
    finally:
        usage.record(time.monotonic() - start, reason, **nums)


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
        self.usage = UsageRecorder()  # what each call cost, for the sidecar

    def chat(self, messages: list[dict], schema: dict, slot: int | None = None) -> dict:
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
            self.url, encode_body(body), {"Content-Type": "application/json"}
        )
        return send(
            request, self.timeout, self.usage, ollama_numbers, lambda r: r["message"]["content"]
        )


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
        self.usage = UsageRecorder()  # shared by all threads, so it has a lock

    def chat(self, messages: list[dict], schema: dict, slot: int | None = None) -> dict:
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
        if slot is not None:
            # Keep each villager's cached prefix in a predictable server slot.
            body.update(id_slot=slot, cache_prompt=True)
        request = urllib.request.Request(
            self.url, encode_body(body), {"Content-Type": "application/json"}
        )
        # IndexError (an empty choices list) is caught inside send.
        return send(
            request, self.timeout, self.usage, llama_numbers,
            lambda r: r["choices"][0]["message"]["content"],
        )  # fmt: skip


class FakeClient:
    """A stand-in for tests. Returns queued replies in order and records every call."""

    def __init__(self, replies: list[dict]):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def chat(self, messages: list[dict], schema: dict, slot: int | None = None) -> dict:
        self.calls.append({"messages": messages, "schema": schema})
        if not self.replies:
            raise LLMError("no queued reply")
        return self.replies.pop(0)
