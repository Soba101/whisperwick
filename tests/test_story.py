"""Story formatting tests. Pure functions over events: no model, no network."""

from helpers import SCENARIO

from whisperwick.events import Event, EventLog
from whisperwick.scenario import load_scenario
from whisperwick.story import format_story, names_from, read_events

NAMES = names_from(load_scenario(SCENARIO))

TALK = Event(
    tick=485, type="talk", actor="npc_victor", location="loc_market",
    data={"to": "npc_bob", "message": "Morning."},
)  # fmt: skip
MOVE = Event(
    tick=490, type="move", actor="npc_hal", location="loc_market",
    data={"from": "loc_town_hall", "to": "loc_market"},
)  # fmt: skip
# Day 2, 00:05 is tick 1445.
NEXT_DAY = TALK.model_copy(update={"tick": 1445})

SIDECAR = {
    "reflections": {"npc_hal": [{"tick": 1320, "text": "Victor looks guilty."}]},
    "secrets": {"murderer": "npc_victor"},
    "stats": {"calls": 10, "rejected": 1},
}


def test_talk_and_move_lines_use_display_names():
    text = format_story([TALK, MOVE], NAMES)
    assert '08:05  Market       Victor -> Bob: "Morning."' in text
    assert "08:10  Hal walks Town Hall -> Market" in text


def test_unknown_names_fall_back_to_ids():
    assert "npc_victor -> npc_bob" in format_story([TALK], {})


def test_events_are_grouped_under_day_headers():
    text = format_story([TALK, NEXT_DAY], NAMES)
    assert text.index("=== Day 1 ===") < text.index("08:05") < text.index("=== Day 2 ===")


def test_reflections_ground_truth_and_stats_are_printed():
    text = format_story([TALK], NAMES, SIDECAR)
    assert 'Night thoughts:\n  Hal: "Victor looks guilty."' in text
    assert "murderer: Victor" in text
    assert "rejection rate 10.0%" in text


def test_no_sidecar_means_no_extras():
    text = format_story([TALK], NAMES)
    assert "Night thoughts" not in text and "Ground truth" not in text


def test_read_events_reads_an_existing_db(tmp_path):
    path = tmp_path / "run.db"
    EventLog(str(path)).append(TALK)
    # A normal EventLog would refuse this file now. read_events must not.
    assert [e.id for e in read_events(path)] == [1]
