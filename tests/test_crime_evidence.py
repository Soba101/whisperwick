"""Each evidence variant has a physical or remembered source."""

import random

import pytest

from whisperwick.crime import check, generate, pools
from whisperwick.crime.characters import populate
from whisperwick.crime.facts import ITEM_CLUES, clues, context, private_memories


@pytest.fixture(scope="module")
def examples():
    jobs, types, weapons = {}, {}, {}
    for seed in range(1000):
        sc = generate(seed)
        s = sc.secrets
        jobs.setdefault(s["accomplice_job"], sc)
        weapons.setdefault(s["weapon"], sc)
        for key in s["clues"]:
            types.setdefault(key, sc)
        if (set(jobs) == {None, *pools.ACCOMPLICE_JOBS}
                and set(types) == set(pools.CLUES) and set(weapons) == set(pools.WEAPONS)):
            return jobs, types, weapons
    pytest.fail("missing evidence variants")


@pytest.mark.parametrize("key", pools.CLUES)
def test_each_selected_clue_must_exist(examples, key):
    sc = examples[1][key].model_copy(deep=True)
    if key == "weapon" or key in ITEM_CLUES:
        suffix = "weapon" if key == "weapon" else ITEM_CLUES[key][0]
        sc.items = [i for i in sc.items if i.id != f"item_crime_{suffix}"]
    else:
        line = pools.CLUES[key].format(**context(sc))
        sc.evidence[sc.secrets["witness"]].remove(line)
    assert not check(sc)


@pytest.mark.parametrize("job", pools.ACCOMPLICE_JOBS)
def test_accomplice_job_has_matching_memory_and_evidence(examples, job):
    sc = examples[0][job].model_copy(deep=True)
    s = sc.secrets
    memory, clue = pools.ACCOMPLICE_JOBS[job]
    assert memory.format(**context(sc)) in sc.evidence[s["accomplice"]]
    items, lines = clues(sc)
    if clue:
        text = clue.format(**context(sc))
        assert any(i.description == text for i in items) or (s["witness"], text) in lines
        # Job evidence is checked as well as the clues pointing at the killer.
        sc.items = [i for i in sc.items if i.description != text]
        sc.evidence[s["witness"]] = [t for t in sc.evidence[s["witness"]] if t != text]
        assert not check(sc)
    else:
        assert "agreed" in memory and "together" in memory
        sc.evidence[s["accomplice"]].remove(memory.format(**context(sc)))
        assert not check(sc)


def test_hidden_weapon_is_really_elsewhere(examples):
    sc = examples[0]["hid_weapon"].model_copy(deep=True)
    s = sc.secrets
    weapon = next(i for i in sc.items if i.id == "item_crime_weapon")
    assert weapon.location == s["weapon_place"] != s["place"]
    assert weapon.location in {loc.id for loc in sc.locations}
    weapon.location = s["place"]
    assert not check(sc)


@pytest.mark.parametrize("weapon", pools.WEAPONS)
def test_weapon_is_a_named_item_with_fitting_trace(examples, weapon):
    sc = examples[2][weapon]
    item = next(i for i in sc.items if i.id == "item_crime_weapon")
    assert item.name == weapon
    assert item.description == context(sc)["weapon_clue"]
    if weapon in ("poisoned mug", "vial of poison"):
        assert "poison" in item.description and "blood" not in item.description


@pytest.mark.parametrize("selected", [["weapon"], ["sighting", "quarrel"], ["weapon", "weapon"]])
def test_insufficient_independent_sources_are_rejected(selected):
    sc = generate(7)
    sc.secrets["clues"] = selected
    # Rebuild the evidence so rejection tests independence, not missing text.
    sc.items, observations = clues(sc)
    populate(sc, random.Random(7))
    for who, text in observations + private_memories(sc):
        sc.evidence[who].append(text)
    assert not check(sc)
