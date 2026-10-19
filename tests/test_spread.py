"""A hand-built relay proves the report follows citations, not nearby speech."""

import json

from scene import belief
from typer.testing import CliRunner

from whisperwick import cli, spread
from whisperwick.belief_log import BeliefLog
from whisperwick.events import Event, EventLog


def fixture_run(tmp_path):
    db = tmp_path / "run.db"
    events = EventLog(str(db))
    log = BeliefLog(db.with_suffix(".beliefs.jsonl"))

    def talk(actor, to, kind, witnesses, subject="npc_victor", **tag):
        return events.append(Event(
            tick=480, type="talk", actor=actor, location="loc_inn", witnesses=witnesses,
            data={"to": to, "message": f"Claim about {subject}",
                  "claim": {"kind": kind, "subject": subject, **tag}},
        ))

    def thinks(npc, after, cited, suspect="npc_victor"):
        log.add(belief(npc, after, suspect=suspect, because=cited))

    def cite(mid, event):
        return {"memory_id": mid, "event_id": event.id, "text": event.data["message"]}

    first = talk("npc_alice", "npc_bob", "killer", ["npc_alice", "npc_bob"])
    # The more recent defence is heard too. Bob's citation still points at e1.
    talk("npc_sarah", "npc_bob", "defends", ["npc_bob"], unverified=True)
    thinks("npc_bob", 2, [cite("m7", first)])
    repeat = talk("npc_bob", "npc_hal", "accuses", ["npc_bob", "npc_hal"])
    thinks("npc_hal", 3, [cite("m2", repeat)])
    events.append(Event(tick=481, type="arrest", actor="npc_hal", location="loc_inn",
                        data={"target": "npc_victor", "reason": "For questioning"}))
    # A later thought must not be mistaken for the belief before the arrest.
    thinks("npc_hal", 4, [], suspect=None)
    events.append(Event(tick=482, type="release", actor="npc_hal", location="loc_inn",
                        data={"target": "npc_victor"}))
    talk("npc_sarah", "npc_hal", "accuses", ["npc_hal"], subject="npc_bob")
    events.db.close()
    return db


def test_command_relay_and_custody(tmp_path):
    db = fixture_run(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    result = CliRunner().invoke(cli.app, ["spread", str(db), "npc_victor"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert out.index("  e1 ") < out.index("  e2 ") < out.index("  e3 ")
    assert "npc_alice -> npc_bob: accuses npc_victor" in out  # Old tag supported.
    assert "defends npc_victor [unverified tag]" in out
    assert "witnesses: npc_bob, npc_hal; preceding belief: b1" in out
    assert "m7 -> e1 heard: npc_alice -> npc_bob" in out
    assert "m2 -> e3 heard: npc_bob -> npc_hal" in out
    assert "npc_hal arrest npc_victor; preceding belief: b2" in out
    assert "npc_hal release npc_victor; preceding belief: b3" in out
    assert "b3 npc_hal after e4: suspect=None" in out
    assert "  e6 " not in out
    assert {p: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_missing_arrest_still_shows_thoughts(tmp_path):
    db = fixture_run(tmp_path)
    events = EventLog.read(str(db))[:3]
    log = BeliefLog.read(db.with_suffix(".beliefs.jsonl"))
    out = spread.render(list(reversed(events)), log, "npc_victor")
    assert "b2 npc_hal after e3" in out
    assert "No arrest/release" in out


def test_no_beliefs_still_shows_events(tmp_path):
    db = fixture_run(tmp_path)
    db.with_suffix(".beliefs.jsonl").unlink()
    out = CliRunner().invoke(cli.app, ["spread", str(db), "npc_victor"])
    assert out.exit_code == 0
    assert "e1 " in out.output and "npc_hal arrest npc_victor" in out.output
    assert "No belief log; citation links unavailable" in out.output
    assert "preceding belief: no logged belief" in out.output


def test_no_claims_and_missing_file(tmp_path):
    db = fixture_run(tmp_path)
    run = CliRunner().invoke
    out = run(cli.app, ["spread", str(db), "npc_nobody"])
    assert out.exit_code == 0 and "No tagged claims" in out.output
    assert "No relevant beliefs" in out.output
    missing = run(cli.app, ["spread", str(tmp_path / "missing.db"), "npc_victor"])
    assert missing.exit_code == 1 and "No such file" in missing.output


def test_citation_receipts_are_not_assumed_heard():
    event = Event(id=1, tick=0, type="talk", actor="npc_bob", location="loc_inn",
                  data={"to": "npc_alice", "message": "Victor did it"})
    log = BeliefLog()
    cites = [{"memory_id": "m0", "event_id": 1, "text": "Victor did it"},
             {"memory_id": "m1", "event_id": None, "text": "starting evidence"},
             {"memory_id": "m2", "event_id": 99, "text": "missing event"}]
    log.add(belief("npc_hal", 1, suspect="npc_victor", because=cites))
    log.add(belief("npc_bob", 1, suspect="npc_victor", because=cites[:1]))
    out = spread.render([event], log, "npc_victor")
    assert "e1 not a recorded witness" in out
    assert "m1 -> no event" in out and "m2 -> e99 (event unavailable)" in out
    assert "e1 own words" in out


def test_sidecar_belief_path(tmp_path):
    db = fixture_run(tmp_path)
    moved = tmp_path / "moved.jsonl"
    db.with_suffix(".beliefs.jsonl").rename(moved)
    db.with_suffix(".json").write_text(json.dumps({"belief_log": str(moved)}))
    result = CliRunner().invoke(cli.app, ["spread", str(db), "npc_victor"])
    assert result.exit_code == 0 and "m7 -> e1 heard" in result.output
