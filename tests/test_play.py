"""Play mode: player scripts and the run-loop hook."""

from pathlib import Path

import pytest
from helpers import fresh_world

from whisperwick.actions import Intent
from whisperwick.llm_sim import run_llm
from whisperwick.player import PLAYER_ID
from whisperwick.player_script import ScriptedPlayer, load_script, parse_at, parse_steps

PLAYERS = Path(__file__).parent.parent / "players"


class LookClient:
    """Always looks; gives a fixed night thought. No network."""

    def chat(self, messages, schema):
        if "thoughts" in schema["properties"]:
            return {"thoughts": "quiet"}
        return {"action": "look", "target": None, "item": None, "message": None}


def say(target, message):
    return Intent(actor=PLAYER_ID, action="talk", target=target, message=message)


# ---- script parsing ----

def test_parse_at_uses_clock_ticks():
    assert parse_at("1 00:00") == 0
    assert parse_at("1 09:00") == 540
    assert parse_at("2 00:01") == 1441


@pytest.mark.parametrize("bad", ["", "09:00", "0 09:00", "1 24:00", "1 09:60", "day 1 09:00"])
def test_bad_times_raise(bad):
    with pytest.raises(ValueError, match="bad time"):
        parse_at(bad)


def test_parse_steps_groups_by_tick_in_file_order():
    _, script = parse_steps({"steps": [
        {"at": "1 09:00", "action": "move", "target": "loc_inn"},
        {"at": "1 09:00", "action": "look"},
    ]})  # fmt: skip
    assert [i.action for i in script[540]] == ["move", "look"]
    assert script[540][0].actor == PLAYER_ID


@pytest.mark.parametrize("bad", [
    {"nope": []},
    {"steps": [], "extra": 1},
    {"steps": "x"},
    {"steps": [{"at": "1 09:00"}]},
    {"steps": [{"at": "1 09:00", "action": "look", "bogus": 1}]},
    {"steps": [{"at": "9am", "action": "look"}]},
])  # fmt: skip
def test_bad_scripts_raise(bad):
    with pytest.raises(ValueError):
        parse_steps(bad)


def test_example_scripts_load():
    assert load_script(PLAYERS / "none.yaml").script == {}
    assert load_script(PLAYERS / "blame_hal.yaml").name == "blame_hal"
    hide = load_script(PLAYERS / "hide_knife.yaml").script
    assert sorted(hide) == [485, 486, 487, 488, 489]


# ---- the run loop ----

def test_run_loop_applies_scripted_intents():
    w = fresh_world()
    # 08:00 start. Talk to Bob at once; then a step the engine must refuse.
    start = w.clock.tick
    notes = []
    player = ScriptedPlayer(
        {start: [say("npc_bob", "Hal did it")], start + 1: [say("npc_alice", "hi")]},
        output_fn=notes.append,
    )
    stats = {}
    memories, _ = run_llm(w, LookClient(), 3, stats=stats, player=player)
    talk = [e for e in w.log.all() if e.type == "talk"]
    assert talk[0].actor == PLAYER_ID and talk[0].data["to"] == "npc_bob"
    # Bob (target) and Victor (overhearer) both remember it.
    assert any("Hal did it" in m.text for m in memories["npc_bob"].memories)
    assert any("Hal did it" in m.text for m in memories["npc_victor"].memories)
    # Alice is at the inn: rejected, recorded, told to the player, run not stopped.
    [rej] = stats["player_rejected"]
    assert rej["tick"] == start + 1 and "not here" in rej["reason"]
    assert rej["intent"]["target"] == "npc_alice" and len(notes) == 1
    assert w.clock.tick == start + 3


def test_scheduler_is_woken_by_a_player_event():
    from whisperwick.player_turn import apply_player_turn
    from whisperwick.scheduler import Scheduler

    w, sched = fresh_world(), Scheduler(["npc_bob", "npc_victor"])
    sched.acted("npc_bob", w.clock.tick)
    sched.acted("npc_victor", w.clock.tick)
    player = ScriptedPlayer({w.clock.tick: [say("npc_bob", "psst")]})
    from whisperwick.memory import Memories

    assert apply_player_turn(w, player, Memories(), sched, {})
    assert sched.woken == {"npc_bob", "npc_victor"}


def test_player_none_changes_nothing():
    a, b = fresh_world(), fresh_world()
    run_llm(a, LookClient(), 30)
    run_llm(b, LookClient(), 30, player=ScriptedPlayer({}))
    assert a.state_hash() == b.state_hash()


def test_player_acts_at_night_and_hide_knife_works():
    w = fresh_world()
    w.clock.advance(14 * 60)  # 22:00: the village sleeps, the player does not
    player = load_script(PLAYERS / "hide_knife.yaml")
    player.script = {w.clock.tick: [say("npc_bob", "anyone?")]}
    run_llm(w, LookClient(), 2, player=player)
    assert any(e.actor == PLAYER_ID for e in w.log.all())


def test_hide_knife_script_moves_the_knife():
    w = fresh_world()
    run_llm(w, LookClient(), 10, player=load_script(PLAYERS / "hide_knife.yaml"))
    assert w.items["item_knife"].location == "loc_temple"


def test_scripted_player_warns_about_steps_before_the_start():
    # A step before the run starts can never run, so the player is told once.
    from whisperwick.player_script import ScriptedPlayer, parse_steps
    from whisperwick.scenario import build_world, load_scenario

    world = build_world(load_scenario("scenarios/murder_of_the_mayor.yaml"))
    _, script = parse_steps({"steps": [{"at": "1 07:00", "action": "look"}]})
    notes = []
    player = ScriptedPlayer(script, output_fn=notes.append)
    assert player.turn(world) == []
    player.turn(world)
    assert len(notes) == 1 and "before the start" in notes[0]
