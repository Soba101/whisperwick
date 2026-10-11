"""Talks to Kev, a local judge model behind a small HTTP API. Standard library only.

Kev is not chat-compatible: one POST carries a text and several named questions, and
the reply holds one answer per question. Nothing is kept between calls, so many
threads can share one client.
"""

import json
import urllib.request

from whisperwick.llm_client import LLMError

MODEL = "kev-latest"


class KevClient:
    def __init__(self, base_url: str, api_key: str | None = None, timeout: int = 120):
        self.base = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:  # only sent when the server has a key set
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def call(self, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data, self.headers())
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                reply = json.load(response)
        except (OSError, ValueError) as e:
            # OSError covers URLError, HTTPError (text too long is a 422) and timeouts.
            raise LLMError(f"kev {path} failed: {e}") from e
        if not isinstance(reply, dict):
            raise LLMError(f"kev {path} gave an unexpected reply")
        return reply

    def ask(self, state: str, questions: dict) -> dict:
        """Ask several questions about one text. Returns {question id: answer}."""
        body = {"state": state, "model": MODEL, "questions": questions}
        answers = self.call("/v1/systemone", body).get("answers")
        if not isinstance(answers, dict):
            raise LLMError("kev reply has no answers")
        return answers

    def models(self) -> dict:
        """The server's model list, used as a connectivity check."""
        return self.call("/v1/models")
