"""replay: state at a tick from events, and the generated page. No network, no model."""

import json
import re

from helpers import SCENARIO
from typer.testing import CliRunner

from whisperwick import cli
from whisperwick.events import Event, EventLog
from whisperwick.replay_data import build_data
from whisperwick.replay_page import render_page
from whisperwick.replay_state import layout, state_at
from whisperwick.scenario import load_scenario

SCEN = load_scenario(SCENARIO)
BAD = "</script><b>x</b>"


def events():
    """Victor walks to the Town Hall, Hal arrests him, then lets him go."""
    mv = {"from": "loc_market", "to": "loc_town_hall"}
    return [
        Event(id=1, tick=490, type="move", actor="npc_victor", location="loc_market", data=mv),
        Event(
            id=2,
            tick=500,
            type="arrest",
            actor="npc_hal",
            location="loc_town_hall",
            data={"target": "npc_victor", "reason": "the knife"},
        ),
        Event(
            id=3,
            tick=510,
            type="talk",
            actor="npc_victor",
            location="loc_town_hall",
            data={
                "to": "npc_hal",
                "message": BAD,
                "claim": {"kind": "defends", "subject": "npc_victor"},
            },
        ),
        Event(
            id=4,
            tick=520,
            type="release",
            actor="npc_hal",
            location="loc_town_hall",
            data={"target": "npc_victor"},
        ),
    ]


def test_state_follows_events():
    start = state_at(SCEN, events(), 480)
    assert start["positions"]["npc_victor"] == "loc_market" and start["held"] == {}
    mid = state_at(SCEN, events(), 505)
    assert mid["positions"]["npc_victor"] == "loc_town_hall"
    assert mid["held"] == {"npc_victor": "npc_hal"}
    assert state_at(SCEN, events(), 520)["held"] == {}


def test_layout_is_fixed_and_covers_every_place():
    assert layout(SCEN) == layout(SCEN)
    assert set(layout(SCEN)) == {p.id for p in SCEN.locations}


def test_page_embeds_json_and_escapes_script_breakouts():
    page = render_page(build_data(SCEN, events(), "none"))
    raw = re.search(r'id="run">(.*?)</script>', page, re.S).group(1)
    data = json.loads(raw)  # the embedded block is valid JSON
    assert any(e.get("text") == BAD for e in data["events"])
    assert BAD not in page and "</script><b>" not in page
    assert page.count("</script>") == 2  # ours only: the data block and the code block


def test_page_has_no_external_urls():
    page = render_page(build_data(SCEN, events()))
    assert not re.search(r'(src|href)\s*=\s*["\']?http', page)
    assert "http" not in page


def test_page_shows_no_secret():
    page = render_page(build_data(SCEN, events()))
    assert "secret" not in page.lower() and "murderer" not in page


def test_cli_writes_the_file(tmp_path):
    db = tmp_path / "run.db"
    log = EventLog(str(db))
    for e in events():
        log.append(e)
    log.db.close()
    out = tmp_path / "x.html"
    result = CliRunner().invoke(cli.app, ["replay", str(db), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert '"npc_victor"' in out.read_text()
    default = CliRunner().invoke(cli.app, ["replay", str(db)])
    assert default.exit_code == 0 and (tmp_path / "run.replay.html").is_file()


def test_cli_missing_db_fails_plainly(tmp_path):
    result = CliRunner().invoke(cli.app, ["replay", str(tmp_path / "none.db")])
    assert result.exit_code == 1
