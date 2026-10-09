# Verifying the world engine

The engine must stay deterministic and strict as it grows.
Run every check before calling engine work done:

```bash
uv run pytest
```

| Check | File | What it proves |
|---|---|---|
| Determinism | `tests/test_determinism.py` | Same seed + same actions = same world (3 seeds x 300 ticks, state hash per tick) |
| Action legality | `tests/test_actions.py` | Bad intents are rejected with a reason, never raise, and change nothing |
| Invariants | `tests/test_invariants.py` | No impossible state after any tick (places exist, time moves forward, log is append-only) |
| Golden snapshot | `tests/test_snapshot.py` | Behaviour does not change by accident |
| Items | `tests/test_items.py` | take/drop/give/show are strict, logged with witnesses, and never leave an item in two places |
| Save/load | `tests/test_save_load.py` | A paused and resumed run ends in the same world as an unbroken one |
| Claims | `tests/test_claims.py` | A talk's claim is well formed, logged with witnesses, never checked for truth; bad ones change nothing |

All checks drive NPCs with the seeded stub agent in `whisperwick/stub_agent.py`.
Never call a real LLM in these checks: LLM output is not repeatable.

## Updating the snapshot on purpose

If you changed behaviour deliberately, look at the diff first, then:

```bash
UPDATE_SNAPSHOTS=1 uv run pytest tests/test_snapshot.py
```

Commit the new snapshot in the same commit as the change that caused it.

## Rule for randomness

Anything random in the engine or the stub agent must use `world.rng`.
Its state is saved in `World.to_dict()`, so resumed runs stay identical.
Using `random.random()` or any other generator will make the
determinism or save/load checks fail. That is the checks doing their job.
