"""Inject broken engine pieces to prove the independent dry-run guard catches them."""

import pytest
from helpers import fresh_world
from made_helpers import make

from whisperwick import made_checks


@pytest.mark.parametrize("damage,reason", [
    ("create", "item count"), ("destroy", "item count"), ("replace", "item count"),
    ("move_other", "other than"), ("kill", "alive"), ("hold", "custody"),
    ("secret", "outside"), ("description", "outside"), ("clock", "outside"),
    ("random", "outside"), ("location_name", "outside"), ("undeclared_item", "outside"),
])
def test_guard_refuses_a_crafted_bad_step(monkeypatch, damage, reason):
    w = fresh_world()
    # This future field must be copied and protected too, even though no piece uses it.
    w.secrets = {"murderer": "npc_victor"}
    before = w.to_dict()
    runner = made_checks.run_step

    def broken(trial, actor, effect, args):
        problem, record = runner(trial, actor, effect, args)
        if damage == "create":
            trial.items["item_fake"] = trial.items["item_boots"].model_copy(
                update={"id": "item_fake"})
        elif damage == "destroy":
            del trial.items["item_knife"]
        elif damage == "replace":
            trial.items["item_fake"] = trial.items.pop("item_knife")
        elif damage == "move_other":
            trial.npcs["npc_bob"].location = "loc_inn"
        elif damage == "kill":
            trial.npcs[actor].alive = False
        elif damage == "hold":
            trial.npcs[actor].held_by = "npc_hal"
        elif damage == "secret":
            trial.secrets["murderer"] = "npc_bob"
        elif damage == "description":
            trial.items["item_boots"].description = "a new object"
        elif damage == "clock":
            trial.clock.advance()
        elif damage == "random":
            trial.rng.random()
        elif damage == "location_name":
            trial.locations["loc_market"].name = "Moon"
        elif damage == "undeclared_item":
            trial.items["item_knife"].known_by = [actor]
        return problem, record

    monkeypatch.setattr(made_checks, "run_step", broken)
    result = make(w, use={"item": "item_boots"})
    assert not result.ok and reason in result.reason
    assert w.to_dict() == before
    assert w.secrets == {"murderer": "npc_victor"} and not w.made_actions
