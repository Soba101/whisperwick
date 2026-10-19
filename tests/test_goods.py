"""Everyday goods use the existing take and give actions."""

import pytest
from helpers import SCENARIO, SEEDS, TICKS, fresh_world, run_ticks
from test_items import intent

from whisperwick.scenario import build_world, load_scenario

GOODS_SCENARIO = SCENARIO.with_name("murder_of_the_mayor_goods.yaml")


@pytest.fixture
def goods_world():
    return build_world(load_scenario(GOODS_SCENARIO))


def test_goods_start_in_their_places(goods_world):
    expected = {
        "item_knife": (None, "loc_town_hall"),
        "item_boots": ("npc_victor", None),
        "item_tea": ("npc_alice", None),
        "item_coffee": ("npc_alice", None),
        "item_bread": ("npc_alice", None),
        "item_stew": ("npc_alice", None),
        "item_mug": ("npc_alice", None),
        "item_ale": ("npc_alice", None),
        "item_cloth": ("npc_victor", None),
        "item_spices": ("npc_victor", None),
        "item_apples": ("npc_victor", None),
        "item_lantern": ("npc_bob", None),
        "item_rope": ("npc_bob", None),
        "item_candle": (None, "loc_temple"),
        "item_prayer_book": (None, "loc_temple"),
    }
    actual = {
        item.id: (item.holder, item.location)
        for item in goods_world.items.values()
        if not item.id.startswith("item_coin_")
    }
    assert actual == expected


def test_each_living_person_has_three_coins(goods_world):
    expected_coins = set()
    for npc in goods_world.npcs.values():
        # Wren's stable actor id is player.
        who = "wren" if npc.id == "player" else npc.id.removeprefix("npc_")
        expected = {f"item_coin_{who}_{number}" for number in range(1, 4)} if npc.alive else set()
        held = {
            item_id for item_id in goods_world.items_held(npc.id)
            if item_id.startswith("item_coin_")
        }
        assert held == expected
        expected_coins.update(expected)
    coins = {key for key in goods_world.items if key.startswith("item_coin_")}
    assert coins == expected_coins
    for key in coins:
        coin = goods_world.items[key]
        assert coin.name == "copper coin"
        assert coin.description == "a small copper coin"
        assert coin.location is None


def test_old_scenario_keeps_only_the_original_items():
    assert set(fresh_world().items) == {"item_knife", "item_boots"}


def test_alice_can_give_coffee_at_the_inn(goods_world):
    assert goods_world.move("player", "loc_inn").ok
    assert goods_world.act(intent("npc_alice", "give", item="item_coffee", target="player")).ok
    assert goods_world.items["item_coffee"].holder == "player"
    assert "item_coffee" not in goods_world.items_held("npc_alice")


def test_wren_can_take_a_temple_candle(goods_world):
    assert goods_world.move("player", "loc_temple").ok
    assert goods_world.act(intent("player", "take", item="item_candle")).ok
    assert goods_world.items["item_candle"].holder == "player"
    assert goods_world.items["item_candle"].location is None


def test_purchase_is_two_chosen_gives(goods_world):
    coin = "item_coin_wren_1"
    assert goods_world.act(intent("player", "give", item=coin, target="npc_victor")).ok
    assert goods_world.items[coin].holder == "npc_victor"
    assert coin not in goods_world.items_held("player")
    assert goods_world.act(intent("npc_victor", "give", item="item_apples", target="player")).ok
    assert goods_world.items["item_apples"].holder == "player"
    assert "item_apples" not in goods_world.items_held("npc_victor")


@pytest.mark.parametrize("seed", SEEDS)
def test_goods_world_is_deterministic(seed):
    # The extra items are in the state hash, so the stub runs must still match.
    def world():
        return build_world(load_scenario(GOODS_SCENARIO), seed=seed)
    assert run_ticks(world(), TICKS) == run_ticks(world(), TICKS)
