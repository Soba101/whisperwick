"""Character and past connections, independent of guilt."""

from whisperwick.crime import pools


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


def allowed_memories(sc):
    villagers = [n for n in sc.npcs if n.id in pools.CAST]
    return {
        n.id: set(pools.WISHES)
        | {
            text.format(other=f"{other.name} ({other.id})")
            for other in villagers
            if other.id != n.id
            for text in pools.RELATIONS
        }
        for n in villagers
    }
