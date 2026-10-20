"""Definitions and invocations go through code checks, including each later use."""

import pytest
from helpers import fresh_world
from made_helpers import HIDE, REVEAL, make

from whisperwick.actions import HANDLERS


@pytest.mark.parametrize("patch", [
    {"name": None}, {"name": "Bad Name"}, {"params": None}, {"params": ["mood"]},
    {"params": ["item", "item"]}, {"needs": ["holds_item"], "params": []},
    {"needs": ["person_here"]}, {"needs": ["at_place:loc_moon"]},
    {"needs": ["magic"]}, {"does": ["create_item"]}, {"does": ["move_person"]},
    {"does": ["arrest"]}, {"does": ["change_custody"]}, {"does": []},
    {"does": ["move_self_exit"]}, {"needs": ["holds_item"] * 2},
])
def test_bad_definition_changes_nothing(patch):
    w = fresh_world()
    before = w.state_hash()
    result = make(w, **patch)
    assert not result.ok and result.reason
    assert w.state_hash() == before and w.made_actions == {}


@pytest.mark.parametrize("name", [*HANDLERS, "recall", "wait"])
def test_every_builtin_name_is_reserved(name):
    w = fresh_world()
    assert not make(w, name=name).ok
    assert not w.log.all()


def test_definition_without_use_checks_shape_without_moving_an_item():
    w = fresh_world()
    # Alice holds nothing: creating a recipe does not require holding its arguments yet.
    result = make(w, actor="npc_alice")
    assert result.ok and result.event.type == "make"
    assert result.event.data["definition"] == {k: v for k, v in HIDE.items() if k != "action"}
    assert w.items["item_boots"].holder == "npc_victor"
    assert not make(w, actor="npc_bob").ok  # names are unique across makers
    assert not w.act({"actor": "npc_bob", "action": "tuck_away", "item": "item_boots"}).ok
    assert not w.act({"actor": "npc_alice", "action": "tuck_away", "item": "item_boots"}).ok
    assert w.act({"actor": "npc_victor", "action": "give", "item": "item_boots",
                  "target": "npc_bob"}).ok


def test_immediate_failure_does_not_register_the_definition():
    w = fresh_world()
    before = w.state_hash()
    result = make(w, actor="npc_alice", use={"item": "item_boots"})
    assert not result.ok and "holding" in result.reason
    assert w.state_hash() == before and w.made_actions == {}


def test_hide_reveal_take_round_trip():
    w = fresh_world()
    assert make(w, use={"item": "item_boots"}).ok
    item = w.items["item_boots"]
    assert item.hidden and item.location == "loc_market" and item.known_by == ["npc_victor"]
    assert make(w, REVEAL, actor="npc_bob", use={}).ok
    assert item.known_by == ["npc_bob", "npc_victor", "player"]
    assert make(w, {"action": "make", "name": "collect", "params": ["item"],
                    "needs": ["item_here"], "does": ["take_item_here"]},
                actor="npc_bob", use={"item": "item_boots"}).ok
    assert item.holder == "npc_bob" and not item.hidden and item.known_by == []


def test_all_steps_are_atomic_and_later_uses_are_checked_again():
    w = fresh_world()
    definition = {**HIDE, "params": ["item", "exit"],
                  "does": ["hide_item_here", "move_self_exit", "take_item_here"]}
    before = w.state_hash()
    assert not make(w, definition, use={"item": "item_boots", "exit": "loc_inn"}).ok
    assert w.state_hash() == before
    assert make(w, use={"item": "item_boots"}).ok
    before = w.state_hash()
    assert not w.act({"actor": "npc_victor", "action": "tuck_away",
                      "item": "item_boots"}).ok
    assert w.state_hash() == before


def test_move_person_place_and_put_pieces():
    w = fresh_world()
    definition = {"action": "make", "name": "set_down_and_leave",
                  "params": ["item", "person", "exit"],
                  "needs": ["holds_item", "person_here", "at_place:loc_market"],
                  "does": ["put_item_here", "move_self_exit"]}
    assert make(w, definition, use={"item": "item_boots", "person": "npc_bob",
                                    "exit": "loc_inn"}).ok
    assert w.npcs["npc_victor"].location == "loc_inn"
    assert w.npcs["npc_bob"].location == "loc_market"
    assert w.items["item_boots"].location == "loc_market"


@pytest.mark.parametrize("args", [{}, {"item": "item_nope"}, {"person": "npc_bob"},
                                  {"item": "item_boots", "actor": "npc_bob"}])
def test_arguments_must_match_params_and_real_ids(args):
    w = fresh_world()
    assert not make(w, use=args).ok
    assert not w.made_actions


def test_custody_cannot_be_bypassed_by_a_made_name():
    w = fresh_world()
    assert make(w).ok
    assert w.move("npc_hal", "loc_market").ok
    assert w.act({"actor": "npc_hal", "action": "arrest", "target": "npc_victor"}).ok
    before = w.state_hash()
    assert not w.act({"actor": "npc_victor", "action": "tuck_away", "item": "item_boots"}).ok
    assert w.state_hash() == before
    assert not make(w, actor="player", name="player_action").ok


def test_hidden_need_and_place_need_are_checked_at_each_use():
    w = fresh_world()
    definition = {**HIDE, "name": "find", "needs": ["item_hidden_here", "at_place:loc_market"],
                  "does": ["reveal_hidden_here"]}
    assert not make(w, definition, use={"item": "item_boots"}).ok
    assert make(w, use={"item": "item_boots"}).ok
    assert make(w, definition, use={"item": "item_boots"}).ok
    assert w.move("npc_victor", "loc_inn").ok
    assert not w.act({"actor": "npc_victor", "action": "find", "item": "item_boots"}).ok


def test_ordered_effects_can_repeat_without_creating_items():
    w = fresh_world()
    definition = {**HIDE, "does": ["hide_item_here", "reveal_hidden_here",
                                  "take_item_here", "hide_item_here"]}
    assert make(w, definition, use={"item": "item_boots"}).ok
    assert w.items["item_boots"].known_by == ["npc_victor"]
    assert w.items["item_boots"].hidden
