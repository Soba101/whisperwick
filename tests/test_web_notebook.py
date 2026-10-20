"""Run the inline controls without sockets; keep notes out of every request body."""

import json
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from whisperwick.web_js import JS
from whisperwick.web_notebook import NOTEBOOK_JS
from whisperwick.web_page import render_page
from whisperwick.web_server import Handler

# A small DOM surface lets the real handlers run when sockets are unavailable.
DOM = """
const assert = require('node:assert/strict');
const elements = new Map(), storage = new Map(), requests = [];
class Element {
  constructor(tag) {
    this.tag = tag; this.children = []; this.value = ''; this.hidden = false;
    this.attrs = {}; this.classes = new Set(); this.textContent = '';
    this.classList = {toggle: (name, on) => on ? this.classes.add(name)
      : this.classes.delete(name)};
    this.style = {};
  }
  appendChild(x) { this.children.push(x); if (x.id) elements.set(x.id, x); return x; }
  replaceChildren(...xs) { this.children = xs; }
  setAttribute(k, v) { this.attrs[k] = v; }
  focus() { document.activeElement = this; }
  querySelector() { return this.children.find(x => x.className === 'reach'); }
  querySelectorAll() { return []; }
}
const get = id => {
  if (!elements.has(id)) elements.set(id, new Element('div'));
  return elements.get(id);
};
const document = {
  getElementById: get, createElement: tag => new Element(tag),
  querySelectorAll: q => q === '.place' ? [...elements.values()].filter(
    x => x.className === 'place') : [],
  addEventListener() {}, body: new Element('body')
};
const localStorage = {
  getItem: key => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, value)
};
const fetch = async (path, options) => {
  requests.push({path, options});
  return {ok: true, json: async () => ({})};
};
const setTimeout = () => {}, location = {reload() {}}, HINTS = {};
"""


def run_controls(code):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is needed to exercise the inline controls")
    # The test drives renders itself instead of starting a polling loop.
    script = DOM + JS + NOTEBOOK_JS.removesuffix("loop();\n") + code
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_notes_are_private_persist_per_game_and_survive_blocked_storage():
    run_controls("""
const state = id => ({game_id: id, known: {people: [], bodies: [], places: [], items: []}});
drawNotebook(state('first'));
$('notes').value = '<img src=x onerror=bad()> private';
$('notes').oninput();
assert.equal(storage.get('whisperwick.notes.first'), $('notes').value);
assert.equal(requests.length, 0);
drawNotebook(state('second'));
assert.equal($('notes').value, '');
drawNotebook(state('first'));
assert.equal($('notes').value, '<img src=x onerror=bad()> private');
localStorage.getItem = localStorage.setItem = () => { throw new Error('blocked'); };
drawNotebook(state('third'));
$('notes').value = 'Still editable';
$('notes').oninput();
$('notes-tab').onclick();
assert.equal($('notes-panel').hidden, false);
assert.equal($('notes').value, 'Still editable');
assert.equal(requests.length, 0);
""")


def test_tabs_use_arrows_home_end_and_restore_the_saved_choice():
    run_controls("""
$('known-tab').onkeydown({key: 'ArrowRight', preventDefault() {}});
assert.equal(document.activeElement, $('notes-tab'));
assert.equal($('notes-tab').attrs['aria-selected'], 'true');
assert.equal($('known-tab').tabIndex, -1);
assert.equal($('known-panel').hidden, true);
assert.equal(storage.get('whisperwick.notebook-tab'), 'notes');
$('notes-tab').onkeydown({key: 'Home', preventDefault() {}});
assert.equal(document.activeElement, $('known-tab'));
$('known-tab').onkeydown({key: 'End', preventDefault() {}});
assert.equal(document.activeElement, $('notes-tab'));
""")
    # Run a fresh page with its persisted tab already saved.
    script = "storage.set('whisperwick.notebook-tab', 'notes');\n" + NOTEBOOK_JS
    node = shutil.which("node")
    result = subprocess.run(
        [
            node,
            "-e",
            DOM
            + JS
            + script.removesuffix("loop();\n")
            + "assert.equal($('notes-panel').hidden, false);",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_temple_marks_only_its_exits_and_changes_marks_after_moving():
    run_controls("""
const places = [
  {id: 'loc_temple', name: 'Temple', x: 10, y: 10, links: []},
  {id: 'loc_market', name: 'Market', x: 20, y: 20, links: []},
  {id: 'loc_inn', name: 'The Inn', x: 30, y: 30, links: []},
  {id: 'loc_town_hall', name: 'Town Hall', x: 40, y: 40, links: []}
];
buildMap(places);
drawMap({place: places[0], exits: [places[1], places[2]], people: [], bodies: []});
assert($('p_loc_town_hall').classes.has('distant'));
assert(!$('p_loc_town_hall').classes.has('can-go'));
assert.equal($('p_loc_market').querySelector('.reach').textContent, 'Can go');
assert($('p_loc_temple').classes.has('here'));
drawMap({place: places[1], exits: [places[0], places[2], places[3]], people: [], bodies: []});
assert(!$('p_loc_town_hall').classes.has('distant'));
assert($('p_loc_town_hall').classes.has('can-go'));
""")


def test_seen_text_stays_text_and_empty_sections_are_clear():
    name = "<img src=x onerror=bad()>"
    run_controls(
        """
drawNotebook({game_id: 'first', known: {people: [], bodies: [], places: [], items: []}});
assert.equal($('known-panel').children.length, 3);
$('known-panel').children.forEach(s => assert.equal(s.children[1].textContent, 'None yet.'));
drawNotebook({game_id: 'first', known: {people: [], bodies: [], items: [],
  places: [{id: 'loc_test', name: NAME}]}});
assert.equal($('known-panel').children[1].children[1].textContent, NAME);
""".replace("NAME", json.dumps(name))
    )
    html = render_page()
    assert 'role="tablist"' in html and 'role="tabpanel"' in html
    assert "Only you can see these notes; the villagers cannot." in html


def test_state_supplies_a_stable_notes_key_without_exposing_the_cookie():
    # Exercise the real route without binding a socket in restricted environments.
    handler = Handler.__new__(Handler)
    handler.hosts, handler.key = {"localhost"}, None
    handler.path = "/state"
    reply = []
    handler.send_json = lambda code, data: reply.append((code, data))

    def state(token):
        handler.headers = {"Host": "localhost", "Cookie": f"ww_game={token}"}
        game = SimpleNamespace(token=token, player=SimpleNamespace(snapshot=lambda _: {}))
        handler.games = SimpleNamespace(
            get=lambda supplied, name=None: game if supplied == token else None)
        handler.do_GET()
        assert reply[-1][0] == 200
        return reply[-1][1]["game_id"]

    first = state("first-game-cookie")
    assert first == state("first-game-cookie")
    assert first != state("second-game-cookie")
    assert "first-game-cookie" not in json.dumps(reply)
