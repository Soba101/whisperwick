"""Check actual starting evidence, rather than trusting a 'solvable' flag."""

import re

from whisperwick.crime import life_pools, pools
from whisperwick.crime.facts import clue_sources, clues, private_memories
from whisperwick.scenario import build_world


def check(sc) -> bool:
    try:
        s = sc.secrets
        killer, victim, accomplice = s["murderer"], s["victim"], s["accomplice"]
        people = {n.id: n for n in sc.npcs}
        if set(people) != {*pools.CAST, "player"}:
            return False
        if killer not in pools.CANDIDATES or victim not in pools.CANDIDATES or killer == victim:
            return False
        if accomplice is not None and accomplice not in set(pools.CAST) - {killer, victim}:
            return False
        innocents = set(pools.CAST) - {killer, victim, accomplice}
        if s["witness"] not in innocents or s["innocent"] not in innocents:
            return False
        if s["place"] not in pools.PLACES or s["hour"] not in pools.HOURS:
            return False
        if s["weapon"] not in pools.WEAPONS or s["motive"] not in pools.MOTIVES:
            return False
        if not 1 <= len(s["misleading"]) <= 2 or len(set(s["misleading"])) != len(s["misleading"]):
            return False
        if not set(s["misleading"]) <= pools.MISLEADING.keys():
            return False
        selected = s["clues"]
        if ("weapon" not in selected or len(set(selected)) != len(selected)
                or not set(selected) <= pools.CLUES.keys() or len(clue_sources(sc)) < 2):
            return False
        job = s["accomplice_job"]
        if (job not in pools.ACCOMPLICE_JOBS if accomplice else job is not None):
            return False
        if s["weapon_place"] not in pools.PLACES or s["trail_place"] not in pools.PLACES:
            return False
        if (s["weapon_place"] != s["place"]) != (job == "hid_weapon"):
            return False
        if s["trail_place"] == s["place"]:
            return False
        if people[victim].alive or people[victim].location != s["place"]:
            return False
        if any(not n.alive for n in sc.npcs if n.id != victim) or sc.authority != ["npc_hal"]:
            return False
        expected_items, observations = clues(sc)
        actual = {i.id: i for i in sc.items}
        # Require independent sources, then verify their actual items and memories.
        if any(actual.get(i.id) != i for i in expected_items):
            return False
        if any(text not in sc.evidence.get(who, []) for who, text in observations):
            return False
        private = private_memories(sc)
        if any(text not in sc.evidence.get(who, []) for who, text in private):
            return False
        # A whitelist also catches paraphrased leaks, not just copied confessions.
        # Every line has a source: character history, an observation, or participation.
        from whisperwick.crime.characters import allowed_memories
        from whisperwick.crime.roles import adapt
        from whisperwick.roles import load_role

        allowed = allowed_memories(sc)
        for who, text in observations + private:
            allowed[who].add(text)
        if sc.role_id:
            role = adapt(load_role(sc.role_id), sc.role_id, sc)
            if role.memory:
                allowed[role.memory.npc].add(role.memory.text)
        if any(
            line not in allowed.get(who, set())
            for who, lines in sc.evidence.items()
            for line in lines
        ):
            return False
        if not lives_ok(sc):
            return False
        world = build_world(sc)
        world.log.db.close()
        return True
    except (KeyError, ValueError, TypeError):
        return False


def lives_ok(sc) -> bool:
    """Week 17: each villager has one routine, worry and secret; none touches the crime."""
    for npc in sc.npcs:
        if npc.id not in pools.CAST:
            continue
        lines = sc.evidence.get(npc.id, [])
        worries = [t for t in lines if t in life_pools.WORRIES]
        secrets = [t for t in lines if t in life_pools.SECRETS]
        routines = [t for t in lines if t in life_pools.ROUTINES[npc.occupation]]
        if len(worries) != 1 or len(secrets) != 1 or len(routines) != 1:
            return False
        if touches_crime(sc, worries[0]) or touches_crime(sc, secrets[0]):
            return False
    return True


def touches_crime(sc, text) -> bool:
    """True if a line names the victim, killer, weapon, murder place or hour, or the motive.

    The motive is checked word by word (words of 4+ letters), so a worry about "a debt"
    cannot sit beside the motive "an unpaid debt" even in other words.
    """
    s = sc.secrets
    names = {n.id: n.name for n in sc.npcs}
    place = next(loc.name for loc in sc.locations if loc.id == s["place"])
    banned = [names[s["victim"]], names[s["murderer"]], s["weapon"], place,
              f"{s['hour']:02d}:", *re.findall(r"[a-z]{4,}", s["motive"].lower())]
    lower = text.lower()
    # Whole words only, so "deal" does not match "ideal"; the hour matches as "22:".
    return any(re.search(rf"(?<![a-z]){re.escape(word.lower())}(?![a-z])", lower)
               for word in banned)
