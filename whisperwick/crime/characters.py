"""Character and past connections, independent of guilt."""

import random

from whisperwick.crime import life_pools, pools


def populate(sc, rng):
    villagers = [n for n in sc.npcs if n.id in pools.CAST]
    for npc in villagers:
        other = rng.choice([n for n in villagers if n.id != npc.id])
        relation = rng.choice(pools.RELATIONS).format(other=f"{other.name} ({other.id})")
        wish = rng.choice(pools.WISHES)
        # Character only. The grudge and the wish are past facts, so they live once,
        # in the villager's own memories, not repeated in the character line.
        sc.personality[npc.id] = " ".join(
            (rng.choice(pools.TEMPERAMENTS), rng.choice(pools.STRANGERS))
        )
        sc.evidence[npc.id] = [relation, wish]
    add_lives(sc, villagers)


def add_lives(sc, villagers):
    """Week 17 (#118): a routine, a worry and a private secret for each villager.

    Their own rng, seeded by the crime number, so the murder facts of every crime
    number stay exactly as before this week. Sampling keeps worries and secrets
    distinct within one village. Memories only: no prompt line points at them.
    """
    life = random.Random(f"lives:{sc.crime_seed}")
    worries = life.sample(life_pools.WORRIES, len(villagers))
    secrets = life.sample(life_pools.SECRETS, len(villagers))
    for npc, worry, secret in zip(villagers, worries, secrets, strict=True):
        routine = life.choice(life_pools.ROUTINES[npc.occupation])
        sc.evidence[npc.id] += [routine, worry, secret]


def allowed_memories(sc):
    villagers = [n for n in sc.npcs if n.id in pools.CAST]
    return {
        n.id: set(pools.WISHES)
        | set(life_pools.ROUTINES[n.occupation])
        | set(life_pools.WORRIES)
        | set(life_pools.SECRETS)
        | {
            text.format(other=f"{other.name} ({other.id})")
            for other in villagers
            if other.id != n.id
            for text in pools.RELATIONS
        }
        for n in villagers
    }
