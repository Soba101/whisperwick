"""The reveal is deterministic, private, and grounded in saved facts."""

from helpers import SCENARIO

from whisperwick.ending_scene import account
from whisperwick.events import Event
from whisperwick.player_ending import PlayerEnding
from whisperwick.scenario import load_scenario


def event(kind, actor="npc_hal", tick=570, **data):
    return Event(type=kind, actor=actor, tick=tick, location="loc_market", data=data)


def reveal(sc, events, target="npc_victor"):
    record = PlayerEnding(sc)
    record.finish(events)
    assert record.choose(target)
    return record.snapshot([])["ending_scene"]


def test_today_account_uses_the_body_place_without_inventing_a_weapon():
    sc = load_scenario(SCENARIO)
    scene = reveal(sc, [])
    assert scene["account"] == "Victor killed Mayor Aldric in Town Hall."
    assert "with" not in scene["account"]


def test_accomplice_is_named_without_inventing_their_part():
    sc = load_scenario(SCENARIO)
    sc.secrets["accomplice"] = "npc_alice"
    assert reveal(sc, [])["account"] == (
        "Victor killed Mayor Aldric in Town Hall. Alice was an accomplice.")


def test_weapon_comes_from_the_secret_item_even_when_other_items_exist():
    sc = load_scenario(SCENARIO.with_name("murder_of_the_mayor_goods.yaml"))
    weapon = sc.items[0]
    sc.secrets["weapon"] = weapon.id
    assert reveal(sc, [])["account"] == (
        f"Victor killed Mayor Aldric in Town Hall with the {weapon.name}.")


def test_account_uses_log_place_or_explicit_crime_place_never_speech():
    names = {"killer": "K", "victim": "V", "loc_market": "Market", "loc_inn": "Inn"}
    secrets = {"murderer": "killer", "victim": "victim"}
    events = [event("talk", actor="killer", message="I used poison at the inn"),
              event("kill", actor="killer", target="victim")]
    assert account(events, names, secrets, "loc_inn") == "K killed V in Market."
    secrets["location"] = "loc_inn"
    assert account(events, names, secrets) == "K killed V in Inn."
    assert account([], names, {}) == "Truth unavailable in this run."


def test_reveal_gate_hides_every_scene_field_until_accusation():
    record = PlayerEnding(load_scenario(SCENARIO))
    assert record.snapshot([])["ending_scene"] is None
    record.finish([event("arrest", target="npc_victor", reason="My words")])
    pending = record.snapshot([])
    assert pending["ending_scene"] is None and pending["ending"] is None
    assert pending["accusation_pending"]
    assert record.choose(None)
    shown = record.snapshot([])
    assert not shown["accusation_pending"]
    assert shown["ending_scene"]["accusation"] == "You named nobody."
    assert shown["ending_scene"]["accusation_correct"] is None


def test_ending_fields_count_player_talks_and_replay_releases():
    sc = load_scenario(SCENARIO)
    sc.player_title = "The mayor's cousin"
    events = [event("arrest", target="npc_victor", reason="First reason"),
              event("release", tick=580, target="npc_victor", reason="Free to go"),
              event("arrest", tick=590, target="npc_bob", reason="Stay here"),
              event("move", actor="npc_victor", to="loc_temple"),
              event("talk", actor="player", to="npc_bob", message="Hello"),
              event("talk", actor="player", to="npc_bob", message="Again"),
              event("talk", actor="npc_bob", to="player", message="Reply"),
              event("talk", actor="npc_bob", to="npc_victor", message="Overheard"),
              event("give", actor="player", to="npc_victor"),
              event("show", actor="player", to="npc_bob")]
    scene = reveal(sc, events, "npc_bob")
    assert scene["role"] == "The mayor's cousin"
    assert scene["accusation"] == "You accused Bob (wrong)."
    assert scene["accusation_correct"] is False
    assert scene["talks"] == [{"id": "npc_bob", "name": "Bob", "count": 2}]
    assert scene["side"] == ["Gives to Victor: 1.", "Shows to Victor: 0."]
    assert scene["custody"] == ["Hal holds at the end: Bob."]
    assert [row["type"] for row in scene["timeline"]] == ["arrest", "release", "arrest"]
    assert scene["timeline"][1]["time"] == "day 1 09:40"
    assert scene["timeline"][1]["words"] == "Free to go"
    assert 'saying: "Free to go"' in scene["timeline"][1]["text"]
    people = {p["id"]: p for p in scene["people"]}
    assert people["npc_bob"]["holder"] == "npc_hal"
    assert people["npc_bob"]["held"]
    assert not people["npc_victor"]["held"]
    assert people["npc_victor"]["place"] == "loc_temple"
    assert "carried" not in people["npc_victor"]
    assert reveal(sc, [], "npc_victor")["accusation_correct"] is True
