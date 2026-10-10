"""outcome: arrests, releases and who is held at the end, from world events only."""

import json

from helpers import SCENARIO, fresh_world
from scene import HAL, belief, new_world, talk
from typer.testing import CliRunner

from whisperwick import cli, compare, compare_outcome, outcome
from whisperwick.belief_log import BeliefLog
from whisperwick.scenario import build_world, load_scenario


def hal_acts(world, action, target):
    r = world.act({"actor": "npc_hal", "action": action, "target": target})
    assert r.ok, r.reason
    return r.event


def hall_world():
    """Hal in the Town Hall with Victor and Bob (the mayor is dead there too)."""
    world = fresh_world()
    for who in ("npc_victor", "npc_bob"):
        assert world.move(who, "loc_town_hall").ok
    return world


def text(world, murderer=None):
    return outcome.format_outcome(world.log.all(), {}, murderer)


def test_nobody_arrested():
    assert text(fresh_world()) == "Nobody was arrested."


def test_one_arrest():
    world = hall_world()
    hal_acts(world, "arrest", "npc_victor")
    out = text(world)
    assert "arrest: npc_hal -> npc_victor (loc_town_hall)" in out
    assert "Held at the end: npc_victor" in out


def test_arrest_then_release():
    world = hall_world()
    hal_acts(world, "arrest", "npc_victor")
    hal_acts(world, "release", "npc_victor")
    out = text(world)
    assert out.index("arrest:") < out.index("release:")
    assert "Held at the end: nobody" in out


def test_two_arrests_and_one_release():
    world = hall_world()
    hal_acts(world, "arrest", "npc_victor")
    hal_acts(world, "arrest", "npc_bob")
    assert outcome.held_at_end(world.log.all()) == ["npc_victor", "npc_bob"]
    hal_acts(world, "release", "npc_victor")
    assert outcome.held_at_end(world.log.all()) == ["npc_bob"]


def test_no_verdict_and_secret_only_when_given():
    world = hall_world()
    hal_acts(world, "arrest", "npc_bob")
    out = text(world)
    assert "right person" not in out and "Scenario secret" not in out
    assert "Scenario secret: murderer = npc_victor" in text(world, "npc_victor")


def test_ignores_dialogue():
    # Talk about an arrest changes nothing: only arrest events count.
    world, memories, _ = new_world()
    talk(world, memories, "npc_victor", "npc_alice", "Hal was arrested", HAL)
    assert text(world) == "Nobody was arrested."


def save_run(tmp_path, name="run.db", release=False):
    db = tmp_path / name
    world = hall_world_at(db)
    hal_acts(world, "arrest", "npc_victor")
    if release:
        hal_acts(world, "release", "npc_victor")
    world.log.db.close()
    db.with_suffix(".json").write_text(json.dumps({"scenario": str(SCENARIO)}))
    return db


def hall_world_at(db):
    world = build_world(load_scenario(SCENARIO), str(db))
    assert world.move("npc_victor", "loc_town_hall").ok
    return world


def test_command(tmp_path):
    db = save_run(tmp_path)
    out = CliRunner().invoke(cli.app, ["outcome", str(db)]).output
    assert "Hal -> Victor (Town Hall)" in out and "Held at the end: Victor" in out
    assert "secret" not in out
    shown = CliRunner().invoke(cli.app, ["outcome", str(db), "--scenario", str(SCENARIO)])
    assert "Scenario secret: murderer = npc_victor" in shown.output
    gone = CliRunner().invoke(cli.app, ["outcome", str(tmp_path / "nope.db")])
    assert gone.exit_code == 1


def test_compare_lines(tmp_path):
    a, b = save_run(tmp_path, "a.db"), save_run(tmp_path, "b.db", release=True)
    # Belief log for run a: aim statuses, one record with no aim_status at all.
    log = BeliefLog(a.with_suffix(".beliefs.jsonl"))
    log.add(belief("npc_hal", 1, aim_status="new"))
    log.add(belief("npc_hal", 2, aim_status="done"))
    log.add(belief("npc_bob", 3))
    runs = [compare.load_run(a), compare.load_run(b)]
    out = compare.format_compare(runs, compare.load_names(runs))
    assert "a.db: Victor" in out and "b.db: nobody" in out
    assert "a.db: new 1 / continuing 0 / done 1 / dropped 0" in out
    assert "b.db: -" in out  # no belief log
    assert compare_outcome.aim_counts(log)["new"] == 1
