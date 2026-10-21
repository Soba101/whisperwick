"""Week 17 (#118): villagers in generated crimes have routines, worries and secrets."""

import re

from whisperwick.crime import generate, life_pools, pools
from whisperwick.crime.check import check, touches_crime
from whisperwick.scenario import load_scenario

BASE = load_scenario(pools.SCENARIOS / "murder_of_the_mayor.yaml")
PLACE_NAMES = {loc.name for loc in BASE.locations}


def lives(sc, npc):
    lines = sc.evidence[npc.id]
    return ([t for t in lines if t in life_pools.ROUTINES[npc.occupation]],
            [t for t in lines if t in life_pools.WORRIES],
            [t for t in lines if t in life_pools.SECRETS])


def test_thousand_crimes_every_villager_has_a_life_apart_from_the_crime():
    for seed in range(1000):
        sc = generate(seed)
        for npc in (n for n in sc.npcs if n.id in pools.CAST):
            routines, worries, secrets = lives(sc, npc)
            assert len(routines) == len(worries) == len(secrets) == 1, (seed, npc.id)
            assert not touches_crime(sc, worries[0]), (seed, worries[0])
            assert not touches_crime(sc, secrets[0]), (seed, secrets[0])
        # Same number, same facts.
        assert generate(seed).evidence == sc.evidence


def test_routines_use_only_real_places_and_daytime_hours():
    for job, lines in life_pools.ROUTINES.items():
        assert len(lines) == 10, job
        for line in lines:
            # Capitalised words are only "I" and real place names.
            rest = line
            for name in PLACE_NAMES:
                rest = rest.replace(name, "")
            assert set(re.findall(r"\b[A-Z][a-z]*", rest)) <= {"I"}, line
            assert any(name in line for name in PLACE_NAMES), line
            # Never in the murder hours (21:00 to 02:00).
            assert all(int(h) < 21 for h in re.findall(r"(\d\d):00", line)), line


def test_checker_refuses_a_worry_or_secret_that_touches_the_crime():
    sc = generate(7)
    s = sc.secrets
    victim = next(n.name for n in sc.npcs if n.id == s["victim"])
    place = next(loc.name for loc in sc.locations if loc.id == s["place"])
    for text in (f"I miss {victim}.", f"I was near the {s['weapon']}.", f"I hate the {place}.",
                 f"I woke at {s['hour']:02d}:00.", f"I worry about {s['motive']}."):
        assert touches_crime(sc, text), text
    assert not touches_crime(sc, "My roof leaks and the autumn rains are near.")
    # A villager with a touching worry is refused by the generator's check.
    npc = next(n for n in sc.npcs if n.id == "npc_hal")
    worry = lives(sc, npc)[1][0]
    sc.evidence["npc_hal"][sc.evidence["npc_hal"].index(worry)] = f"I miss {victim}."
    assert not check(sc)
    # Missing a secret is refused too.
    sc = generate(7)
    sc.evidence["npc_bob"] = [t for t in sc.evidence["npc_bob"] if t not in life_pools.SECRETS]
    assert not check(sc)
