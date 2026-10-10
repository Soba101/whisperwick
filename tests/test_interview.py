"""Interview, sidecar extras and the compare report. Fake clients only, no network."""

import json
from pathlib import Path

from helpers import SCENARIO, fresh_world
from typer.testing import CliRunner

from whisperwick import cli, compare, compare_command, interview, llm_run, run_report
from whisperwick.events import Event
from whisperwick.llm_client import FakeClient
from whisperwick.memory import Memories
from whisperwick.scenario import build_world, load_scenario
from whisperwick.story import names_from

NAMES = names_from(load_scenario(SCENARIO))
NPCS = ["npc_bob", "npc_hal"]


def counts(world, memories):
    return len(world.log.all()), {k: len(v.memories) for k, v in memories.items()}


def test_interview_good_replies_and_error_reply():
    w, mem = fresh_world(), Memories()
    mem["npc_bob"].add(0, "I saw the knife in the Town Hall.", 5)
    client = FakeClient([{"suspect": "npc_victor", "why": "He had the knife."}])  # then runs dry
    stats = {}
    out = interview.interview(w, mem, client, NPCS, stats)
    assert out["npc_bob"] == {"suspect": "npc_victor", "why": "He had the knife."}
    assert out["npc_hal"]["suspect"] is None and out["npc_hal"]["why"].startswith("error:")
    assert stats["interview_errors"] == 1
    # One call each, in sorted order, with the question and the murder-related memory.
    assert len(client.calls) == 2
    msgs = client.calls[0]["messages"]
    assert "Who do you think killed Mayor Aldric?" in msgs[1]["content"]
    assert "I saw the knife" in msgs[0]["content"]


def test_interview_rejects_unknown_suspect_and_bad_shape():
    client = FakeClient([{"suspect": "npc_nobody", "why": "x"}, {"why": "no suspect key"}])
    out = interview.interview(fresh_world(), Memories(), client, NPCS)
    assert all(a["suspect"] is None and a["why"].startswith("error") for a in out.values())


def test_interview_is_read_only_and_schema_lists_the_living():
    w, mem = fresh_world(), Memories()
    mem["npc_bob"].add(0, "something", 3)
    before = counts(w, mem)
    client = FakeClient([{"suspect": None, "why": "no idea"}] * 2)
    interview.interview(w, mem, client, NPCS)
    assert counts(w, mem) == before  # no events, no new memories
    assert "npc_hal" not in mem  # nobody got a stream just by being asked
    enum = client.calls[0]["schema"]["properties"]["suspect"]["enum"]
    assert None in enum and "player" in enum and "npc_bob" in enum  # asker and player included
    assert "npc_mayor" not in enum  # the dead cannot be accused-by-id here
    assert client.calls[0]["schema"]["properties"]["why"]["maxLength"] == 300


def test_final_items_and_summary_lines():
    w = fresh_world()
    items = run_report.final_items(w)
    assert items["item_knife"] == {"location": "loc_town_hall", "holder": None}
    answers = {
        "npc_bob": {"suspect": "npc_hal", "why": ""},
        "npc_hal": {"suspect": None, "why": ""},
    }
    assert run_report.summary_lines(answers, NAMES) == ["  Bob -> Hal", "  Hal -> no idea"]


# ---- compare ----


def make_run(name, sidecar, events=()):
    return {"name": name, "events": list(events), "sidecar": sidecar}


KNIFE = Event(
    tick=486, type="take", actor="player", location="loc_town_hall",
    data={"item": "item_knife", "item_name": "bloody knife", "to": None},
)  # fmt: skip
NEW = {
    "player": "blame_hal",
    "stats": {"calls": 10, "rejected": 1},
    "interview": {
        "npc_bob": {"suspect": "npc_hal", "why": "x"},
        "npc_hal": {"suspect": "npc_victor", "why": "y"},
        "npc_victor": {"suspect": None, "why": "z"},
    },
    "items": {"item_knife": {"location": None, "holder": "player"}},
}


def test_compare_formats_new_and_old_runs():
    text = compare.format_compare(
        [make_run("new.db", NEW, [KNIFE]), make_run("old.db", {"stats": {"calls": 4}})], NAMES
    )
    assert "new.db" in text and "blame_hal" in text and "10.0%" in text
    assert "new.db: Hal 1, Victor 1, none 1" in text
    assert "old.db: -" in text  # an old run still shows, with dashes
    assert "knife: held by Wren" in text  # the item shows by its scenario name
    assert "Wren takes the bloody knife" in text
    row = next(x for x in text.splitlines() if x.strip().startswith("Bob"))
    assert "Hal" in row and row.rstrip().endswith("-")


def test_compare_caps_event_lines_and_handles_empty_sidecar():
    many = [KNIFE.model_copy(update={"tick": 486 + i}) for i in range(20)]
    lines = compare.key_events(make_run("a.db", {}, many), NAMES)
    assert len(lines) == 1 + compare.MAX_EVENT_LINES + 1 and lines[-1] == "  ... and 5 more"
    assert compare.suspect_table([make_run("a.db", {})], NAMES) == ["Suspects: -"]


def test_compare_columns_fit_long_run_names():
    long = "w3-blame_hal_with_a_long_name.db"
    runs = [make_run(long, NEW), make_run("b.db", NEW)]
    header = compare.header_rows(runs)
    assert header[1].startswith(long + "  ") and header[2].startswith("b.db" + " " * 30)
    suspects = compare.suspect_table(runs, NAMES)
    # The second run's column starts two spaces after the long name ends.
    assert suspects[1].index("b.db") == suspects[1].index(long) + len(long) + 2


def test_compare_event_lines_show_the_day():
    day2 = KNIFE.model_copy(update={"tick": 1440 + 7 * 60 + 1})
    lines = compare.key_events(make_run("a.db", {}, [KNIFE, day2]), NAMES)
    assert lines[1].startswith("  d1 08:06") and lines[2].startswith("  d2 07:01")


def test_compare_cli_smoke(tmp_path):
    dbs = []
    for n in ("a", "b"):
        db = tmp_path / f"{n}.db"
        world = build_world(load_scenario(SCENARIO), str(db))
        world.act({"actor": "player", "action": "move", "target": "loc_inn"})
        world.log.db.commit()
        side = {**NEW, "scenario": str(SCENARIO)}
        llm_run.write_sidecar(llm_run.sidecar_path(db), side)
        dbs.append(str(db))
    result = CliRunner().invoke(cli.app, ["compare", *dbs])
    assert result.exit_code == 0, result.output
    assert "a.db: Hal 1, Victor 1, none 1" in result.output
    assert "Wren walks" in result.output  # a player event
    missing = CliRunner().invoke(cli.app, ["compare", dbs[0], str(tmp_path / "nope.db")])
    assert missing.exit_code == 1 and "No such file" in missing.output
    assert compare_command.compare_runs  # the command body lives in its own module


class InterviewClient:
    """Looks in the game; names Victor in the interview."""

    def chat(self, messages, schema):
        # A thought also has a "suspect", so tell the two apart by "thoughts" first.
        if "thoughts" in schema["properties"]:
            return {"thoughts": "quiet", "suspect": "npc_victor", "sureness": "unsure",
                    "because": [], "trust": []}  # fmt: skip
        if "suspect" in schema["properties"]:
            return {"suspect": "npc_victor", "why": "He did it."}
        return {"action": "look", "target": None, "item": None, "message": None}


def test_run_stores_interview_and_items_in_sidecar(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.settings, "llm_base_url", lambda: "http://x")
    monkeypatch.setattr(cli.settings, "llm_model", lambda: "m")
    monkeypatch.setattr(cli, "make_client", lambda server, url, model: InterviewClient())
    db = tmp_path / "r.db"
    result = CliRunner().invoke(cli.app, ["run", "--agent", "llm", "--hours", "1", "--db", str(db)])
    assert result.exit_code == 0, result.output
    side = json.loads(Path(db).with_suffix(".json").read_text())
    assert side["interview"]["npc_bob"]["suspect"] == "npc_victor"
    assert "npc_mayor" not in side["interview"] and "player" not in side["interview"]
    assert side["items"]["item_knife"]["location"] == "loc_town_hall"
    assert "  Bob -> Victor" in result.output
    # The thoughts were saved next to the db, and the sidecar says where.
    assert side["belief_log"] == str(db.with_suffix(".beliefs.jsonl"))
