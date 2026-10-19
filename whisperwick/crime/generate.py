"""Build a crime once, before any agent takes a turn."""

import random

from whisperwick.crime import pools
from whisperwick.crime.characters import populate
from whisperwick.crime.facts import clues, private_memories
from whisperwick.scenario import Scenario, load_scenario


def draw(base, goods, seed, rng):
    sc = base.model_copy(deep=True)
    sc.name, sc.seed = "generated_crime", seed
    sc.crime_seed = seed
    sc.evidence, sc.personality, sc.items = {}, {}, []
    killer, victim = rng.sample(pools.CANDIDATES, 2)
    survivors = [n for n in pools.CAST if n not in (killer, victim)]
    accomplice = rng.choice(survivors) if rng.randrange(4) == 0 else None
    witnesses = [n for n in survivors if n != accomplice]
    place = rng.choice(pools.PLACES)
    sc.secrets = dict(
        murderer=killer,
        victim=victim,
        accomplice=accomplice,
        motive=rng.choice(pools.MOTIVES),
        weapon=rng.choice(pools.WEAPONS),
        place=place,
        hour=rng.choice(pools.HOURS),
        witness=rng.choice(witnesses),
        innocent=rng.choice(witnesses),
        misleading=rng.sample(["quarrel", "visit"], rng.randint(1, 2)),
    )
    for npc in sc.npcs:
        npc.alive = npc.id != victim
        if npc.id == victim:
            npc.location = place
    populate(sc, rng)
    items, lines = clues(sc)
    sc.items.extend(items)
    for who, line in lines + private_memories(sc):
        sc.evidence[who].append(line)
    # Draw from the existing goods pool, grouped by their original place.
    # Ground placement avoids leaving a dead shopkeeper holding goods.
    homes = {n.id: n.location for n in base.npcs}
    for loc in pools.PLACES:
        pool = [
            i
            for i in goods.items
            if i.id not in {"item_knife", "item_boots"}
            and (i.location or homes.get(i.holder)) == loc
        ]
        chosen = rng.sample(pool, rng.randint(1, len(pool)))
        # Food is part of every crime, even when the random mix was all durable goods.
        food = [i for i in pool if i.consumable]
        if food and not any(i.consumable for i in chosen):
            chosen.append(rng.choice(food))
        sc.items.extend(i.model_copy(update={"holder": None, "location": loc}) for i in chosen)
    sc.facts = [f"{n.name} ({n.id}) is the {n.occupation}." for n in sc.npcs if n.id in pools.CAST]
    return sc


def generate(seed: int) -> Scenario:
    """Same seed gives the same accepted draw without touching the engine RNG."""
    from whisperwick.crime.check import check

    rng = random.Random(seed)
    base = load_scenario(pools.SCENARIOS / "murder_of_the_mayor.yaml")
    goods = load_scenario(pools.SCENARIOS / "murder_of_the_mayor_goods.yaml")
    # A failed draw consumes this RNG; retries remain reproducible.
    for _ in range(100):
        sc = draw(base, goods, seed, rng)
        if check(sc):
            return sc
    raise ValueError(f"no solvable crime after 100 draws for seed {seed}")
