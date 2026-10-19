"""Endings use physical events and secrets, never dialogue or model judgements."""

import json

import pytest
from helpers import SCENARIO

from whisperwick import ending, outcome_command
from whisperwick.events import Event, EventLog
from whisperwick.player_ending import PlayerEnding
from whisperwick.scenario import load_scenario
from whisperwick.story import names_from

SC = load_scenario(SCENARIO)


def event(kind, actor="npc_hal", target="npc_victor", tick=570, **data):
    return Event(type=kind, actor=actor, tick=tick, location="loc_market",
                 data={"target": target, **data})


def test_truth_hal_custody_and_arrest_times_follow_log():
    events = [event("arrest"), event("release", tick=580),
              event("arrest", target="npc_bob", tick=590),
              event("arrest", actor="npc_alice", target="npc_sarah", tick=591)]
    text = ending.report(events, names_from(SC), SC.secrets, SC.authority, {"target": "npc_victor"})
    assert "The truth: Victor killed Mayor Aldric." in text
    assert "Hal holds at the end: Bob." in text
    assert "day 1 09:30  arrest: Hal -> Victor" in text
    assert "day 1 09:50  arrest: Hal -> Bob" in text
    assert "arrest: Alice" not in text
    assert "You accused Victor (right)." in text


@pytest.mark.parametrize("accusation,phrase", [
    (None, "No accusation recorded."), ({"target": None}, "You named nobody."),
    ({"target": "npc_bob"}, "You accused Bob (wrong)."),
])
def test_accusation_states(accusation, phrase):
    assert phrase in ending.report([], names_from(SC), SC.secrets, SC.authority, accusation)


def test_side_counts_only_gives_and_shows_visible_to_victor():
    events = [event("give", "player", to="npc_victor"),
              event("show", "player", to="npc_victor"),
              event("show", "player", to="npc_bob"),
              event("give", "npc_bob", to="npc_victor"),
              event("talk", "player", to="npc_victor", message="I warned you"),
              event("show", "player")]
    events[-1].witnesses = ["npc_victor"]
    events.append(event("show", "player"))  # Victor was elsewhere.
    text = ending.report(events, names_from(SC), SC.secrets, SC.authority)
    assert "Gives to Victor: 1." in text and "Shows to Victor: 2." in text
    assert "good" not in text and "evil" not in text and "warned" not in text


def test_private_record_is_once_only_saved_and_does_not_touch_events(tmp_path):
    record = PlayerEnding(SC)
    assert not record.choose("npc_victor")  # The day is still running.
    events = [event("arrest")]
    record.finish(events)
    assert record.snapshot([])["ending"] is None
    assert not record.choose("made_up") and not record.choose(["npc_victor"])
    side = tmp_path / "run.json"
    side.write_text(json.dumps({"secrets": SC.secrets, "seed": 42}))
    record.sidecar = side
    before = [e.model_dump() for e in events]
    assert record.choose("npc_victor") and not record.choose("npc_bob")
    assert [e.model_dump() for e in events] == before
    assert json.loads(side.read_text())["accusation"] == {"target": "npc_victor"}
    assert json.loads(side.read_text())["seed"] == 42
    assert "(right)" in record.snapshot([])["ending"]


def test_accusation_before_sidecar_is_bound_is_saved_later(tmp_path):
    record = PlayerEnding(SC)
    record.finish([])
    assert record.choose(None)
    record.sidecar = tmp_path / "late.json"
    record.sidecar.write_text("{}")
    record.save()
    assert json.loads(record.sidecar.read_text())["accusation"] == {"target": None}


def test_outcome_uses_saved_truth_and_accusation_when_scenario_is_gone(tmp_path):
    db = tmp_path / "run.db"
    log = EventLog(str(db))
    log.append(event("arrest"))
    log.db.close()
    db.with_suffix(".json").write_text(json.dumps({
        "scenario": "/gone.yaml", "secrets": SC.secrets, "authority": SC.authority,
        "accusation": {"target": "npc_bob"}}))
    text = outcome_command.outcome_run(db)
    assert "npc_victor killed npc_mayor" in text
    assert "You accused npc_bob (wrong)" in text
    assert "day 1 09:30" in text


def test_ending_uses_all_scenario_authorities_and_actual_murderer():
    sc = SC.model_copy(deep=True)
    sc.authority = ["npc_alice", "npc_sarah"]
    sc.secrets["murderer"] = "npc_bob"
    events = [event("arrest", "npc_alice", "npc_bob"),
              event("release", "npc_sarah", "npc_bob", tick=580),
              event("arrest", "npc_sarah", "npc_victor", tick=590),
              event("arrest", "npc_hal", "npc_bob", tick=591),
              event("give", "player", to="npc_bob"),
              event("give", "player", to="npc_victor"),
              event("show", "player", to="npc_bob"),
              event("show", "player", to="npc_victor"),
              event("show", "player")]
    events[-1].witnesses = ["npc_bob"]
    text = ending.report(events, names_from(sc), sc.secrets, sc.authority)
    assert "The truth: Bob killed Mayor Aldric." in text
    assert "Alice holds at the end: nobody." in text
    assert "Sarah holds at the end: Victor." in text
    assert "day 1 09:30  arrest: Alice -> Bob" in text
    assert "day 1 09:50  arrest: Sarah -> Victor" in text
    assert "Hal" not in text
    assert "Gives to Bob: 1." in text and "Shows to Bob: 2." in text
    assert "Gives to Victor" not in text and "Shows to Victor" not in text


def test_missing_truth_does_not_count_interactions_with_an_unknown_murderer():
    text = ending.report([event("show", "player")], names_from(SC), {}, [])
    assert "Truth unavailable" in text
    assert "Gives to" not in text and "Shows to" not in text


def test_player_ending_passes_scenario_authority_and_murderer():
    sc = SC.model_copy(deep=True)
    sc.authority = ["npc_alice"]
    sc.secrets["murderer"] = "npc_bob"
    sc.player_title = "A private role"
    record = PlayerEnding(sc)
    record.finish([event("arrest", "npc_alice", "npc_bob"),
                   event("give", "player", to="npc_bob")])
    assert record.choose("npc_bob")
    text = record.snapshot([])["ending"]
    assert "Alice holds at the end: Bob." in text
    assert "Gives to Bob: 1." in text
    assert "Your role: A private role." in text


def test_saved_outcome_passes_authority_and_title_without_scenario(tmp_path):
    db = tmp_path / "run.db"
    log = EventLog(str(db))
    log.append(event("arrest", "npc_alice", "npc_bob"))
    log.append(event("give", "player", to="npc_bob"))
    log.db.close()
    db.with_suffix(".json").write_text(json.dumps({
        "scenario": "/gone.yaml", "secrets": {"murderer": "npc_bob", "victim": "npc_mayor"},
        "authority": ["npc_alice"], "player_title": "A private role"}))
    text = outcome_command.outcome_run(db)
    assert "npc_alice holds at the end: npc_bob." in text
    assert "Gives to npc_bob: 1." in text
    assert "Your role: A private role." in text
