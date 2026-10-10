"""Run several slow calls at the same time, and give the results back in the same order.

The model is slow, so waiting for one villager at a time wastes the machine. The caller
sends the calls out together, then applies the results itself in a fixed order, so the
run stays the same as a one-by-one run.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor


def run_all(calls: list[Callable[[], object]], workers: int) -> list:
    """Run every call. Result i belongs to call i. A call that raised leaves its exception.

    workers <= 1 runs them inline, one by one, with no threads at all.
    """

    def safe(call):
        # Never raise out of here: one failed call must not stop the others.
        try:
            return call()
        except Exception as e:
            return e

    if workers <= 1 or len(calls) <= 1:
        return [safe(c) for c in calls]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # map() yields in input order, whatever order the calls finish in.
        return list(pool.map(safe, calls))
