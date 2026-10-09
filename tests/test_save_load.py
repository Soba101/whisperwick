"""Check 5, save/load round-trip: saving and loading changes nothing.

Long experiment runs will be paused and resumed. A resumed run must end in
exactly the same world as one that never stopped, including what the
random generator does next.
"""

import json

from helpers import fresh_world, run_ticks

from whisperwick.world import World


def test_save_then_load_matches_uninterrupted_run():
    first, second = 150, 150

    # Run A: no interruption.
    straight = fresh_world(seed=7)
    run_ticks(straight, first + second)

    # Run B: stop halfway, save to JSON text, load into a brand-new world, carry on.
    # Nothing is shared between the two halves except the saved text.
    paused = fresh_world(seed=7)
    run_ticks(paused, first)
    saved = json.dumps(paused.to_dict())
    resumed = World.from_dict(json.loads(saved))
    run_ticks(resumed, second)

    assert resumed.state_hash() == straight.state_hash()
