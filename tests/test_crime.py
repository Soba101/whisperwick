"""Starting crimes are code facts, reproducible and independently inspectable."""

import pytest
from helpers import run_ticks

from whisperwick.crime import check, generate, pools
from whisperwick.crime.facts import private_memories
from whisperwick.roles import ROLE_IDS, apply_role
from whisperwick.scenario import build_world, load_scenario


def test_thousand_crimes():
    accomplices = 0
    seen = {key: set() for key in ("weapon", "motive", "accomplice_job", "clues")}
    for seed in range(1000):
        sc = generate(seed)
        assert check(sc), seed
        assert sc == generate(seed), seed
        s = sc.secrets
        for key in seen:
            seen[key].update(s[key] if key == "clues" else [s[key]])
        assert s["murderer"] not in ("npc_hal", "player")
        assert s["victim"] not in ("npc_hal", "player")
        accomplices += s["accomplice"] is not None
        assert {n.id for n in sc.npcs} == {*pools.CAST, "player"}
        assert any(i.consumable for i in sc.items)
        assert all(any(i.location == loc for i in sc.items) for loc in pools.PLACES)
        private = [text for _, text in private_memories(sc)]
        for who, lines in sc.evidence.items():
            if who not in (s["murderer"], s["accomplice"]):
                assert not any(text in line for text in private for line in lines)
        assert set(sc.personality) == set(pools.CAST)
        for role in ROLE_IDS:
            chosen = apply_role(sc, role)
            assert check(chosen)
            if role == "cousin":
                assert next(n.name for n in sc.npcs if n.id == s["victim"]) in chosen.player_title
            if role == "partner":
                assert next(n.name for n in sc.npcs if n.id == s["murderer"]) in chosen.player_title
    assert 0.2 <= accomplices / 1000 <= 0.3
    assert seen["weapon"] == set(pools.WEAPONS)
    assert seen["motive"] == set(pools.MOTIVES)
    assert seen["accomplice_job"] == {None, *pools.ACCOMPLICE_JOBS}
    assert seen["clues"] == set(pools.CLUES)


@pytest.mark.parametrize("seed", [1, 7, 42])
def test_same_crime_same_stub_events(seed):
    a, b = build_world(generate(seed)), build_world(generate(seed))
    assert run_ticks(a, 300) == run_ticks(b, 300)
    assert a.log.all() == b.log.all()
    a.log.db.close()
    b.log.db.close()


@pytest.mark.parametrize("damage", ["weapon", "physical", "witness", "leak", "paraphrase", "body"])
def test_checker_refuses_broken_evidence(damage):
    sc = generate(7)
    if damage == "weapon":
        sc.items = [i for i in sc.items if i.id != "item_crime_weapon"]
    elif damage == "physical":
        # Choose a draw with a physical clue besides the weapon.
        sc = next(generate(seed) for seed in range(20)
                  if any(i.id == "item_crime_cuff" for i in generate(seed).items))
        sc.items = [i for i in sc.items if i.id != "item_crime_cuff"]
    elif damage == "witness":
        sc.evidence[sc.secrets["witness"]] = []
    elif damage == "leak":
        sc.evidence["npc_hal"].append(private_memories(sc)[0][1])
    elif damage == "paraphrase":
        sc.evidence["npc_hal"].append("Sarah murdered Bob.")
    else:
        next(n for n in sc.npcs if n.id == sc.secrets["victim"]).alive = True
    assert not check(sc)


def test_retries_use_the_same_seeded_stream(monkeypatch):
    import importlib

    module = importlib.import_module("whisperwick.crime.check")
    real = module.check
    seen = []

    def reject_first(sc):
        seen.append(sc.model_dump())
        return len(seen) % 2 == 0 and real(sc)

    monkeypatch.setattr(module, "check", reject_first)
    a, b = generate(7), generate(7)
    assert a == b and len(seen) == 4
    assert seen[0] != seen[1]


@pytest.mark.parametrize("filename", ["murder_of_the_mayor", "murder_of_the_mayor_goods"])
def test_crime_absent_preserves_scenario_and_stub_events(filename):
    from whisperwick.crime.selection import select

    path = pools.SCENARIOS / f"{filename}.yaml"
    legacy, selected = load_scenario(path), select(path)
    assert legacy == selected and selected.crime_seed is None
    a, b = build_world(legacy), build_world(selected)
    assert run_ticks(a, 300) == run_ticks(b, 300)
    a.log.db.close()
    b.log.db.close()
