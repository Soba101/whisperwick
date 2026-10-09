"""Trace: the chain behind a lie, from a saved run. No model."""

import json

from helpers import SCENARIO
from test_belief_report import make_run, talk

from whisperwick import belief_report, story, trace, trace_command
from whisperwick.beliefs import BeliefState, Source
from whisperwick.scenario import build_world, load_scenario

SC = load_scenario(SCENARIO)
NAMES = story.names_from(SC)


def text_for(tmp_path, subject="npc_hal"):
    return trace_command.trace_run(make_run(tmp_path), subject)


def test_trace_shows_full_chain_and_the_made_up_lie(tmp_path):
    text = text_for(tmp_path)
    print(text)
    lines = text.splitlines()
    assert lines[0] == "Who believes Hal (npc_hal) killed the mayor?"
    # Alice (25%) heard Bob, who heard the player, who had nothing behind it.
    assert "Alice (npc_alice) 25%   trusts Bob 35%, Wren 30%" in text
    assert "<- told by Bob (npc_bob), event 3" in text
    assert "   <- told by Wren (player), event 1, day 1 08:00" in text
    assert "      Wren had no source: made up (a guess or a lie)" in text
    # Bob's trust in Wren dropped from 0.3 to 0.15: the lie clashed with what he saw.
    assert "Bob (npc_bob) 15%   trusts Wren 15%" in text
    # The end of the report lists every villager's trust in the player.
    assert "Trust in the player:\n  Alice (npc_alice) 30%\n  Bob (npc_bob) 15%" in text


def test_trace_a_teller_with_a_saw_source_shows_the_note(tmp_path):
    db = tmp_path / "saw.db"
    w = build_world(SC, str(db))
    assert w.act({"actor": "npc_bob", "action": "move", "target": "loc_inn"}).ok
    talk(w, "npc_bob", "npc_alice", "killer", "npc_victor")  # Bob really saw Victor
    w.log.db.close()
    text = trace_command.trace_run(db, "npc_victor")
    assert "<- told by Bob (npc_bob), event 2" in text
    assert "   <- saw: saw Victor hurrying from the Town Hall (at the start)" in text
    assert "made up" not in text


def test_teller_speaking_about_himself_is_not_a_lie():
    state = BeliefState.from_scenario(SC)
    state.conf = {"npc_a": {"npc_hal": 0.4}}
    state.sources = {"npc_a": {"npc_hal": [Source("told", "npc_hal", 5, 480, "said innocent")]}}
    data = trace.build_trace(state, "npc_hal")
    inner = data["believers"][0]["sources"][0]["sources"][0]
    assert inner["kind"] == "self" and inner["by"] == "npc_hal"
    text = trace.format_trace(data, NAMES)
    assert "Hal was speaking about themselves" in text
    assert "made up" not in text


def test_self_loop_ends_and_long_chain_is_cut():
    state = BeliefState.from_scenario(SC)
    # Event ids only go down along a chain, so a real loop cannot happen: a teller who
    # "heard it from himself" at the same event has nothing before it, so it ends as made up.
    state.conf = {"npc_a": {"x": 0.5}}
    state.sources = {"npc_a": {"x": [Source("told", "npc_a", 5, 480, "said killer")]}}
    inner = trace.build_trace(state, "x")["believers"][0]["sources"][0]["sources"][0]
    assert inner["kind"] == "own"
    # A straight chain p0 <- p1 <- p2 ... with falling event ids is cut at MAX_DEPTH.
    n = trace.MAX_DEPTH + 4
    state.conf = {f"p{i}": {"x": 0.5} for i in range(n + 1)}
    state.sources = {
        f"p{i}": {"x": [Source("told", f"p{i + 1}", 100 - i, 480, "said killer")]} for i in range(n)
    }
    first = trace.build_trace(state, "x")
    first["believers"] = first["believers"][:1]  # only p0, so the others do not add lines
    text = trace.format_trace(first, {})
    assert "chain cut here" in text
    assert f"told by p{trace.MAX_DEPTH + 1}" in text
    assert f"told by p{trace.MAX_DEPTH + 2}" not in text


def test_trace_json_has_the_same_structure(tmp_path):
    db = make_run(tmp_path)
    data = json.loads(trace_command.trace_run(db, "npc_hal", as_json=True))
    assert data["subject"] == "npc_hal"
    alice = next(b for b in data["believers"] if b["id"] == "npc_alice")
    told_by_bob = alice["sources"][0]
    assert (told_by_bob["by"], told_by_bob["event_id"]) == ("npc_bob", 3)
    told_by_player = told_by_bob["sources"][0]
    assert told_by_player["by"] == "player" and told_by_player["sources"][0]["kind"] == "own"
    assert data["trust_in_player"]["npc_bob"] == 0.15
    assert [b["confidence"] for b in data["believers"]] == sorted(
        (b["confidence"] for b in data["believers"]), reverse=True
    )


def test_trace_nobody_believes(tmp_path):
    text = trace_command.trace_run(make_run(tmp_path), "npc_sarah")
    assert "Nobody." in text


def test_trace_works_on_an_old_run_with_no_claims(tmp_path):
    db = tmp_path / "old.db"
    w = build_world(SC, str(db))
    w.log.db.close()
    text = trace_command.trace_run(db, "npc_victor")
    assert "<- saw: saw Victor hurrying from the Town Hall (at the start)" in text
    assert belief_report.scenario_for_run(db).name == "murder_of_the_mayor"
