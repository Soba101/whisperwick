"""Uniform seeded samples of the turns the normal scheduler actually asks for."""

import random

from whisperwick.screen_replay import difference, replay


def pick(dbs, acts=300, thinks=50, seed=9):
    """Choose repeatable turn samples only from runs that replay faithfully."""
    if acts < 0 or thinks < 0:
        raise ValueError("turn counts must be nonnegative")
    pools = {"act": [], "think": []}
    # Repeated input paths must not give one run extra sampling weight.
    sources = list(dict.fromkeys(str(db) for db in dbs))
    for db in sources:
        # Scheduler callbacks include quiet looks that leave no saved event.
        def collect(c, npc, kind, db=db):
            """Save stable turn coordinates so scoring can rebuild this context."""
            pools[kind].append({"db": db, "tick": c.world.clock.tick, "npc": npc, "kind": kind})
        source, c = replay(db, collect)
        try:
            # Reject drifting runs before their turns become a saved sample.
            drift = difference(source, c)
            if drift:
                raise ValueError(f"{db}: {drift}")
        finally:
            c.world.log.db.close()
    # A local seeded generator makes selection repeatable without changing other randomness.
    rng = random.Random(seed)
    # Sampling all turns together preserves their natural mix across source runs.
    turns = rng.sample(pools["act"], acts) + rng.sample(pools["think"], thinks)
    return {"seed": seed, "source_runs": sources, "turns": turns}
