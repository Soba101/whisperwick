"""Check actual starting evidence, rather than trusting a 'solvable' flag."""

from whisperwick.crime import pools
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
        world = build_world(sc)
        world.log.db.close()
        return True
    except (KeyError, ValueError, TypeError):
        return False
