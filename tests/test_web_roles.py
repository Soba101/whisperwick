"""Exercise real routes and browser handlers without opening a socket."""

import json
import shutil
import subprocess
import threading

from helpers import SCENARIO
from test_web_notebook import DOM

from whisperwick import web_play
from whisperwick.player_web import WebPlayer
from whisperwick.roles import apply_role
from whisperwick.scenario import build_world, load_scenario
from whisperwick.web_ending import ENDING_JS
from whisperwick.web_games import GameManager
from whisperwick.web_js import JS
from whisperwick.web_notebook import NOTEBOOK_JS
from whisperwick.web_server import Handler

SC = load_scenario(SCENARIO)


def manager():
    calls = []

    def launch(role):
        calls.append(role)
        return WebPlayer(apply_role(SC, role, 1)), threading.Thread()

    return GameManager(launch, choose_roles=True, default_role="partner"), calls


def handler(games, path, body=None, token=None):
    h = Handler.__new__(Handler)
    h.games, h.path, h.key, h.hosts = games, path, None, {"localhost"}
    h.headers = {"Host": "localhost", "Cookie": f"ww_game={token}" if token else ""}
    h.read_body = lambda: body
    replies = []
    h.send_json = lambda code, data, cookies=None: replies.append((code, data, cookies))
    h.send = lambda code, data, kind, cookies=None: replies.append((code, data, cookies))
    h.do_POST() if body is not None else h.do_GET()
    return replies[-1]


def test_picker_precedes_world_creation_and_is_per_visitor():
    games, calls = manager()
    assert handler(games, "/")[0] == 200
    assert handler(games, "/state")[1] == {"select_role": True, "default_role": "partner"}
    assert calls == [] and games.games == {}
    assert handler(games, "/newgame", {"role": "bad"})[0] == 400
    assert handler(games, "/newgame", {"role": "peddler"})[0] == 200
    first = next(iter(games.games.values()))
    assert first.player.sc.role_id == "peddler"
    assert handler(games, "/newgame", {"role": "partner"})[0] == 200
    assert calls == ["peddler", "partner"]
    assert games.games[first.token].player.sc.evidence == SC.evidence
    assert handler(games, "/choose", {}, first.token)[0] == 200
    assert first.player.stopped and first.token not in games.games
    assert handler(games, "/state", token=first.token)[1]["select_role"]


def test_private_fact_then_accusation_then_ending_no_world_mutation(tmp_path):
    games, _ = manager()
    game = games.replace(None, "partner")
    p = game.player
    world = build_world(p.sc)
    with p.cv:
        p._refresh(world)
    assert p.snapshot()["known"]["private_fact"] == p.sc.private_fact
    assert p.snapshot()["you"]["title"] == p.sc.player_title
    assert p.snapshot()["you"]["occupation"] == "newcomer"
    assert p.snapshot()["ending"] is None
    assert handler(games, "/accuse", {"target": "npc_victor"}, game.token)[0] == 409
    p.finish()
    before = world.state_hash(), world.log.all()
    assert p.snapshot()["accusation_pending"] and p.snapshot()["secret"] is None
    assert handler(games, "/accuse", {"target": "npc_missing"}, game.token)[0] == 409
    assert handler(games, "/accuse", {"target": "npc_victor"}, game.token)[0] == 200
    assert "Victor killed Mayor Aldric" in p.snapshot()["ending"]
    assert "You accused Victor (right)" in p.snapshot()["ending"]
    assert f"Your role: {p.sc.player_title}." in p.snapshot()["ending"]
    assert (world.state_hash(), world.log.all()) == before
    assert handler(games, "/accuse", {"target": "npc_bob"}, game.token)[0] == 409
    world.log.db.close()


def test_launcher_uses_per_game_role_and_keeps_minutes(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(web_play, "run_with_llm", lambda *a, **kw: seen.append(a))
    launch = web_play.launcher(SC, SCENARIO, lambda n: str(tmp_path / f"{n}.db"), 7, 4320)
    a, ta = launch("partner")
    b, tb = launch("peddler")
    ta.join(2)
    tb.join(2)
    assert {call[0].role_id for call in seen} == {"partner", "peddler"}
    assert all(call[3:5] == (7, 4320) for call in seen)
    assert a.sc is not b.sc and a.sc.role_id == "partner" and b.sc.role_id == "peddler"


def test_real_inline_picker_accusation_and_private_fact_controls():
    node = shutil.which("node")
    assert node  # The existing notebook tests exercise the same runtime.
    # Give the small DOM fixture the select APIs these controls need.
    setup = """
function Option(name, id) { this.name = name; this.value = id; }
Object.defineProperty(Element.prototype, 'options', {get() { return this.children; }});
"""
    checks = """
assert.equal(drawRolePicker({select_role: true, default_role: 'partner'}), true);
assert.equal($('role').value, 'partner');
assert.equal($('role-picker').hidden, false);
$('start-game').focus();
drawRolePicker({select_role: true});
assert.equal(document.activeElement, $('start-game'));
drawRolePicker({select_role: false});
assert.equal($('role-picker').hidden, true);
drawEnd({finished: true, accusation_pending: true, accusation_choices: [
  {id: 'npc_victor', name: 'Victor'}]});
assert.equal($('accusation').hidden, false);
assert.equal($('end').hidden, true);
$('accused').value = 'npc_victor';
$('record-accusation').onclick();
assert.equal(requests[0].path, '/accuse');
assert.deepEqual(JSON.parse(requests[0].options.body), {target: 'npc_victor'});
drawEnd({finished: true, accusation_pending: false, ending: 'The truth: saved facts.'});
assert.equal($('accusation').hidden, true);
assert.equal($('outcome').textContent, 'The truth: saved facts.');
drawNotebook({known: {people: [], bodies: [], places: [], items: [],
  private_fact: '<b>A fact</b>'}});
assert.equal($('known-panel').children[0].children[1].textContent, '<b>A fact</b>');
"""
    script = DOM + setup + JS + ENDING_JS + NOTEBOOK_JS.removesuffix("loop();\n") + checks
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "/accuse" not in json.dumps(SC.evidence)


def test_web_run_binds_sidecar_before_late_accusation(monkeypatch, tmp_path):
    from test_play_terminal import fake_setup

    from whisperwick.llm_cli import run_with_llm

    fake_setup(monkeypatch)
    sc = apply_role(SC, "partner", 4)
    p = WebPlayer(sc)
    p.wait_left = 1  # Let a whole short run finish without human input.
    db = tmp_path / "web.db"
    run_with_llm(sc, SCENARIO, str(db), 4, 1, p, "web")
    p.finish()
    assert p.ending.choose("npc_victor")
    saved = json.loads(db.with_suffix(".json").read_text())
    assert saved["accusation"] == {"target": "npc_victor"}
    assert saved["role"] == "partner" and saved["private_fact"] == sc.private_fact
    p.world.log.db.close()
