"""Counts what the model server was asked and what it cost, one record per call.

Pure bookkeeping: nothing here changes a request or a reply. Clients are shared by
several threads (parallel_calls.py), so every write goes through a lock.
"""

import math
import threading


def get_int(d, *keys):
    """Dig through nested dicts with .get. Returns None if anything is missing or odd."""
    for key in keys:
        d = d.get(key) if isinstance(d, dict) else None
    return d if isinstance(d, int | float) and not isinstance(d, bool) else None


def llama_numbers(reply) -> dict:
    """Token counts and timings from a llama-server reply. Missing fields stay None."""
    n = get_int(reply, "timings", "predicted_n")
    ms = get_int(reply, "timings", "predicted_ms")
    cached = get_int(reply, "usage", "prompt_tokens_details", "cached_tokens")
    if cached is None:
        cached = get_int(reply, "timings", "cache_n")
    return {
        "prompt": get_int(reply, "usage", "prompt_tokens"),
        "output": get_int(reply, "usage", "completion_tokens"),
        "cached": cached,
        "prompt_ms": get_int(reply, "timings", "prompt_ms"),
        "ms_per_token": ms / n if ms is not None and n else None,
    }


def ollama_numbers(reply) -> dict:
    """Token counts from an Ollama reply. It has no cache count and no per-token timing."""
    return {
        "prompt": get_int(reply, "prompt_eval_count"),
        "output": get_int(reply, "eval_count"),
    }


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _total(values):
    values = [v for v in values if v is not None]
    return sum(values) if values else None


def _p90(values):
    """Nearest-rank 90th percentile: deterministic, no interpolation."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(0.9 * len(ordered)) - 1]


class UsageRecorder:
    def __init__(self):
        self._lock = threading.Lock()
        self._calls: list[dict] = []

    def record(self, seconds: float, reason: str | None = None, **numbers) -> None:
        """reason=None means the call worked. numbers: prompt, output, cached, prompt_ms,
        ms_per_token (any may be missing)."""
        with self._lock:
            self._calls.append({"seconds": seconds, "reason": reason, **numbers})

    def summary(self) -> dict:
        """A plain JSON-able dict for the sidecar. None where nothing was reported."""
        with self._lock:
            calls = list(self._calls)
        reasons: dict[str, int] = {}
        for c in calls:
            if c["reason"]:
                reasons[c["reason"]] = reasons.get(c["reason"], 0) + 1
        seconds = [c["seconds"] for c in calls]
        return {
            "requests": len(calls),
            "errors": sum(1 for c in calls if c["reason"]),
            "error_reasons": dict(sorted(reasons.items())),
            "prompt_tokens": _total(c.get("prompt") for c in calls),
            "output_tokens": _total(c.get("output") for c in calls),
            "cached_tokens": _total(c.get("cached") for c in calls),
            "latency_mean_s": _mean(seconds),
            "latency_p90_s": _p90(seconds),
            "prompt_ms_mean": _mean(c.get("prompt_ms") for c in calls),
            "ms_per_output_token_mean": _mean(c.get("ms_per_token") for c in calls),
        }
