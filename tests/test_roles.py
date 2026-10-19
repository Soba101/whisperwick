"""Role boundaries, private facts, and events captured from main before this change."""

import hashlib
import json
import random
from pathlib import Path

import pytest
from pydantic import ValidationError

from whisperwick.player_script import load_script
from whisperwick.roles import ROLE_IDS, Role, apply_role, load_role
from whisperwick.scenario import build_world, load_scenario
from whisperwick.stub_agent import intents_for_tick

SCENARIOS = ("murder_of_the_mayor", "murder_of_the_mayor_goods")


@pytest.mark.parametrize("filename", SCENARIOS)
@pytest.mark.parametrize("role_id", ROLE_IDS)
def test_overlay_changes_only_allowed_starting_facts(filename, role_id):
    sc = load_scenario(f"scenarios/{filename}.yaml")
    before = sc.model_dump()
    role = load_role(role_id)
    chosen = apply_role(sc, role_id, 7)
    assert sc.model_dump() == before  # No state leaks to another visitor.
    assert chosen.personality == sc.personality and chosen.secrets == sc.secrets
    assert chosen.authority == sc.authority and chosen.locations == sc.locations
    for old, new in zip(sc.npcs, chosen.npcs, strict=True):
        if old.id == "player":
            assert new.model_dump(exclude={"name", "occupation"}) == old.model_dump(
                exclude={"name", "occupation"})
            assert new.name == role.player.name and new.occupation == role.player.occupation
        else:
            assert old == new
    assert chosen.items[:len(sc.items)] == sc.items
    assert all(i.holder == "player" for i in chosen.items[len(sc.items):])
    expected = {k: list(v) for k, v in sc.evidence.items()}
    if role.memory:
        expected.setdefault(role.memory.npc, []).append(role.memory.text)
    assert chosen.evidence == expected
    assert chosen.player_title == role.player.title
    assert chosen.private_fact == random.Random(7).choice(sc.facts)
    build_world(chosen).log.db.close()


@pytest.mark.parametrize("key", ["personality", "rules", "prompts", "secrets", "authority"])
def test_role_rejects_forbidden_overlay_fields(key):
    data = load_role("peddler").model_dump()
    with pytest.raises(ValidationError):
        Role.model_validate({**data, key: {"npc_victor": "trust Wren"}})
    with pytest.raises(ValidationError):
        Role.model_validate({**data, "player": {**data["player"], key: "anything"}})


def test_role_cannot_move_other_peoples_items_or_add_many_memories():
    data = load_role("partner").model_dump()
    data["items"][0]["holder"] = "npc_victor"
    with pytest.raises(ValidationError, match="role items"):
        Role.model_validate(data)
    data = load_role("partner").model_dump()
    data["memory"] = [data["memory"], data["memory"]]
    with pytest.raises(ValidationError):
        Role.model_validate(data)
    with pytest.raises(ValueError, match="unknown role"):
        load_role("../partner")


@pytest.mark.parametrize("filename", SCENARIOS)
def test_pool_is_public_true_facts_not_secret_or_victors_line(filename):
    sc = load_scenario(f"scenarios/{filename}.yaml")
    # Each authored fact corresponds to a real starting record, not a verdict.
    expected = {f"{n.name} ({n.id}) is the {n.occupation}." for n in sc.npcs
                if n.id in ("npc_alice", "npc_bob", "npc_sarah")}
    expected |= {"Victor (npc_victor) is a merchant.", "Hal (npc_hal) is the village guard.",
                 "A bloody kitchen knife lies in the Town Hall (loc_town_hall).",
                 "Victor (npc_victor) wears muddy boots."}
    assert set(sc.facts) == expected
    items = {i.id: i for i in sc.items}
    assert items["item_knife"].location == "loc_town_hall"
    assert items["item_boots"].holder == "npc_victor"
    for fact in sc.facts:
        assert fact not in sc.evidence["npc_victor"]
        assert "killed" not in fact and "murderer" not in fact
        assert fact not in sc.secrets.values()


def test_fact_draw_uses_run_seed_and_never_consumes_engine_randomness():
    sc = load_scenario("scenarios/murder_of_the_mayor.yaml")
    draws = {apply_role(sc, "cousin", seed).private_fact for seed in range(12)}
    assert len(draws) > 1
    assert apply_role(sc, "partner").private_fact == apply_role(sc, "partner", sc.seed).private_fact
    assert apply_role(sc, "partner", 1).private_fact == apply_role(sc, "partner", 1).private_fact
    a, b = build_world(sc, seed=9), build_world(apply_role(sc, "peddler", 9), seed=9)
    assert a.rng.getstate() == b.rng.getstate()
    a.log.db.close()
    b.log.db.close()


@pytest.mark.parametrize("filename", SCENARIOS)
@pytest.mark.parametrize("seed", [1, 42])
def test_no_role_none_script_matches_main_stub_events(filename, seed):
    fixture = json.loads(Path("tests/fixtures/week13_main_events.json").read_text())
    sc = load_scenario(f"scenarios/{filename}.yaml")
    assert apply_role(sc, None, seed) is sc
    world = build_world(apply_role(sc, None, seed), seed=seed)
    player = load_script("players/none.yaml")
    for _ in range(fixture["ticks"]):
        assert player.turn(world) == []
        world.step(intents_for_tick(world))
    payload = json.dumps([e.model_dump() for e in world.log.all()], sort_keys=True)
    assert hashlib.sha256(payload.encode()).hexdigest() == fixture["sha256"][f"{filename}:{seed}"]
    world.log.db.close()


def test_overlay_refuses_missing_pool_unknown_memory_and_item_collision(monkeypatch):
    import whisperwick.roles as roles

    sc = load_scenario("scenarios/murder_of_the_mayor.yaml")
    with pytest.raises(ValueError, match="facts pool"):
        apply_role(sc.model_copy(update={"facts": []}), "partner")
    role = load_role("partner")
    role.memory.npc = "npc_typo"
    monkeypatch.setattr(roles, "load_role", lambda _: role)
    with pytest.raises(ValueError, match="unknown npc"):
        apply_role(sc, "partner")
    role.memory.npc = "npc_victor"
    role.items[0].id = "item_knife"
    with pytest.raises(ValueError, match="already exists"):
        apply_role(sc, "partner")
