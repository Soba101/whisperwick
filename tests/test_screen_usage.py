"""Per-turn accounting keeps the server's numbers and restores its recorder."""

from whisperwick.call_usage import UsageRecorder
from whisperwick.llm_client import LLMError
from whisperwick.screen_usage import MeasuredClient


def test_native_usage_including_failure_is_preserved():
    class Recorded:
        def __init__(self):
            self.usage = UsageRecorder()
            self.n = 0

        def chat(self, messages, schema):
            self.n += 1
            self.usage.record(self.n, "bad JSON" if self.n == 2 else None,
                              prompt=10, output=5, cached=2, prompt_ms=100, ms_per_token=4)
            if self.n == 2:
                raise LLMError("broken", "bad JSON")
            return {"action": "look"}

    client = Recorded()
    original = client.usage
    measured = MeasuredClient(client)
    measured.chat([], {})
    try:
        measured.chat([], {})
    except LLMError:
        pass
    summary = measured.usage.summary()
    assert summary["requests"] == 2 and summary["errors"] == 1
    assert summary["prompt_tokens"] == 20 and summary["output_tokens"] == 10
    assert summary["latency_mean_s"] == 1.5 and summary["latency_p90_s"] == 2
    # Server timings survive, so network delay can be told apart from model time.
    assert summary["prompt_ms_mean"] == 100 and summary["ms_per_output_token_mean"] == 4
    assert client.usage is original
