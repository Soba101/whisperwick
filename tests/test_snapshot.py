"""Check 4, golden snapshot: behaviour does not change by accident.

A fixed seeded run is compared with a saved copy in tests/snapshots/.
A difference is not always a bug, but it must be a choice. To accept a change:
    UPDATE_SNAPSHOTS=1 uv run pytest tests/test_snapshot.py
"""

import json
import os
from pathlib import Path

from helpers import fresh_world, run_ticks

SNAPSHOT = Path(__file__).parent / "snapshots" / "murder_seed42_300_ticks.json"


def test_world_matches_golden_snapshot():
    world = fresh_world(seed=42)
    run_ticks(world, ticks=300)
    actual = world.to_dict()
    # The random generator's raw state is 600+ numbers of noise. Determinism and
    # save/load already cover it, so leave it out of the readable snapshot.
    actual.pop("rng")

    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n")

    assert SNAPSHOT.exists(), "no snapshot yet: run with UPDATE_SNAPSHOTS=1 to create it"
    expected = json.loads(SNAPSHOT.read_text())
    assert actual == expected, "world changed: if intended, rerun with UPDATE_SNAPSHOTS=1"
