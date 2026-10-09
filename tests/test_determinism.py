"""Check 1, determinism: same seed + same actions = same world, every time.

Without this, no experiment result can be trusted or reproduced.
"""

import pytest
from helpers import SEEDS, TICKS, fresh_world, run_ticks


@pytest.mark.parametrize("seed", SEEDS)
def test_same_seed_same_world(seed):
    a = run_ticks(fresh_world(seed), TICKS)
    b = run_ticks(fresh_world(seed), TICKS)
    # Report the FIRST tick that differs: that is where the bug starts.
    first_diff = next((t for t, (x, y) in enumerate(zip(a, b, strict=True)) if x != y), None)
    assert first_diff is None, f"seed {seed}: worlds diverge at tick {first_diff}"


def test_different_seeds_differ():
    """Guards against a check that passes because nothing happens at all."""
    assert run_ticks(fresh_world(1), TICKS)[-1] != run_ticks(fresh_world(2), TICKS)[-1]
