"""Keep the normal client's token and latency accounting for each screened request."""

import time

from whisperwick.call_usage import UsageRecorder


class MeasuredClient:
    """Keep screen costs comparable to the normal request accounting."""
    def __init__(self, client):
        """Keep screen accounting separate from the wrapped client totals."""
        self.client = client
        self.usage = UsageRecorder()
        self.records = []

    def chat(self, messages, schema, **kwargs):
        """Measure each request so retries and failures remain visible in screen costs."""
        one = UsageRecorder()
        old = getattr(self.client, "usage", None)
        # Native clients record even failed requests. Fakes need only a clock.
        if old is not None:
            self.client.usage = one
        start = time.monotonic()
        error = None
        try:
            return self.client.chat(messages, schema, **kwargs)
        except Exception as exc:
            error = getattr(exc, "reason", "bad reply")
            raise
        finally:
            # Restore shared client accounting even when a request raises.
            if old is not None:
                self.client.usage = old
            summary = one.summary()
            seconds = summary["latency_mean_s"]
            # Clients without usage support still contribute elapsed time.
            seconds = time.monotonic() - start if seconds is None else seconds
            numbers = {"prompt": summary["prompt_tokens"], "output": summary["output_tokens"],
                       "cached": summary["cached_tokens"]}
            # Retain request costs so combined reports can recompute their totals.
            self.usage.record(seconds, error, **numbers)
            self.records.append({"seconds": seconds, "reason": error, **numbers})
