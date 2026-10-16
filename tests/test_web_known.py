"""Sightings use only filtered views and never follow people elsewhere."""

from helpers import SCENARIO, fresh_world

from whisperwick.actions import Intent
from whisperwick.player import PLAYER_ID
from whisperwick.player_web import WebPlayer
from whisperwick.scenario import load_scenario
from whisperwick.web_known import Known
from whisperwick.web_state import you_view


def see(known, world):
    known.update(you_view(world))
    return known.snapshot()


def move(world, place):
    assert world.act(Intent(actor=PLAYER_ID, action="move", target=place)).ok


def test_people_keep_last_sighting_and_exclude_unseen_people():
    world, known = fresh_world(), Known()
    first = see(known, world)
    assert [p["id"] for p in first["people"]] == ["npc_bob", "npc_victor"]
    assert first["bodies"] == [] and first["items"] == []
    move(world, "loc_temple")
    world.clock.tick += 12
    later = see(known, world)
    bob = next(p for p in later["people"] if p["id"] == "npc_bob")
    assert bob["place"] == {"id": "loc_market", "name": "Market"}
    assert bob["clock"] == first["people"][0]["clock"]
    assert "npc_alice" not in {p["id"] for p in later["people"]}
    assert [p["id"] for p in later["places"]] == ["loc_market", "loc_temple"]
    move(world, "loc_market")
    assert len(see(known, world)["places"]) == 2


def test_held_status_is_from_last_sighting_only():
    world, known = fresh_world(), Known()
    world.npcs["npc_bob"].held_by = "npc_hal"
    first = see(known, world)
    assert first["people"][0]["held"]
    move(world, "loc_temple")
    world.npcs["npc_bob"].held_by = None
    assert see(known, world)["people"][0]["held"]
    move(world, "loc_market")
    assert not see(known, world)["people"][0]["held"]


def test_ground_carried_dropped_and_given_items():
    world, known = fresh_world(), Known()
    move(world, "loc_town_hall")
    ground = see(known, world)["items"][0]
    assert ground["id"] == "item_knife" and not ground["carried"]
    assert ground["place"]["id"] == "loc_town_hall"
    assert world.act(Intent(actor=PLAYER_ID, action="take", item="item_knife")).ok
    assert see(known, world)["items"][0]["carried"]
    move(world, "loc_market")
    assert world.act(Intent(actor=PLAYER_ID, action="drop", item="item_knife")).ok
    dropped = see(known, world)["items"][0]
    assert not dropped["carried"] and dropped["place"]["id"] == "loc_market"
    assert world.act(Intent(actor=PLAYER_ID, action="take", item="item_knife")).ok
    see(known, world)
    assert world.act(Intent(actor=PLAYER_ID, action="give", item="item_knife", target="npc_bob")).ok
    given = see(known, world)["items"][0]
    assert not given["carried"] and given["place"] == dropped["place"]
    assert given["clock"] == dropped["clock"]
    move(world, "loc_temple")
    assert see(known, world)["items"][0] == given


def test_bodies_keep_first_sighting():
    world, known = fresh_world(), Known()
    move(world, "loc_town_hall")
    first = see(known, world)["bodies"]
    assert [b["id"] for b in first] == ["npc_mayor"]
    world.clock.tick += 9
    assert see(known, world)["bodies"] == first


def test_records_are_detached_sorted_and_keyed_by_id():
    view = you_view(fresh_world())
    view["people"][0]["name"] = view["people"][1]["name"] = "Same name"
    known = Known()
    known.update(view)
    view["place"]["name"] = "Changed later"
    first = known.snapshot()
    assert [p["id"] for p in first["people"]] == ["npc_bob", "npc_victor"]
    assert first["people"][0]["place"]["name"] == "Market"
    first["people"][0]["name"] = "Changed snapshot"
    assert known.snapshot()["people"][0]["name"] == "Same name"


def test_web_player_updates_knowledge_and_new_games_start_empty():
    world = fresh_world()
    player = WebPlayer(load_scenario(SCENARIO))
    with player.cv:
        player._refresh(world)
    assert [p["id"] for p in player.snapshot()["known"]["people"]] == ["npc_bob", "npc_victor"]
    assert WebPlayer(load_scenario(SCENARIO)).snapshot()["known"] == {
        "people": [],
        "bodies": [],
        "places": [],
        "items": [],
    }


def test_an_item_first_seen_in_hand_does_not_invent_a_ground_sighting():
    world, known = fresh_world(), Known()
    # A gift may be carried before the next view, without ever lying on the ground.
    view = you_view(world)
    view["carried"] = [{"id": "item_gift", "name": "Gift"}]
    known.update(view)
    assert known.snapshot()["items"][0]["carried"]
    view["carried"] = []
    known.update(view)
    item = known.snapshot()["items"][0]
    assert not item["carried"] and "place" not in item
    assert item["carried_place"] == view["place"]
