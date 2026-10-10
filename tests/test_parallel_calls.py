"""run_all: same order out as in, exceptions kept in place, no threads when workers is 1."""

import threading

from whisperwick.parallel_calls import run_all


def test_results_keep_input_order_even_if_calls_finish_out_of_order():
    gate = threading.Event()

    def slow():
        gate.wait(5)  # finishes only after the fast one
        return "slow"

    def fast():
        gate.set()
        return "fast"

    assert run_all([slow, fast], 2) == ["slow", "fast"]


def test_a_failing_call_leaves_its_exception_and_the_rest_still_run():
    def boom():
        raise ValueError("no")

    for workers in (1, 3):
        got = run_all([lambda: 1, boom, lambda: 3], workers)
        assert got[0] == 1 and got[2] == 3
        assert isinstance(got[1], ValueError)


def test_one_worker_runs_inline_on_the_calling_thread():
    seen = []
    run_all([lambda: seen.append(threading.current_thread()) for _ in range(3)], 1)
    assert seen == [threading.current_thread()] * 3


def test_empty_list_is_fine():
    assert run_all([], 4) == []
