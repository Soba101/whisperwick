"""Exercise both reveal UIs without sockets or a graphics driver."""

import json
import subprocess
from importlib.resources import files

from test_web_notebook import DOM

from whisperwick.web_ending import ENDING_JS
from whisperwick.web_js import JS

# Native dialog semantics are the only browser APIs missing in the small fixture.
DIALOG = """
Element.prototype.append = function(...xs) { xs.forEach(x => this.appendChild(x)); };
Element.prototype.showModal = function() { this.open = true; this.opens = (this.opens || 0)+1; };
Element.prototype.close = function() { this.open = false; };
document.querySelector = () => get('footer');
document.body.classList.add = name => document.body.classes.add(name);
document.body.classList.remove = name => document.body.classes.delete(name);
function Option(name, id) { this.name = name; this.value = id; }
Object.defineProperty(Element.prototype, 'options', {get() { return this.children; }});
const text = n => [n.textContent,...(n.children || []).map(text)].join(' ');
"""
SCENE = json.dumps({
    "account": "Victor killed Mayor Aldric in Town Hall.",
    "custody": ["Hal holds at the end: nobody."],
    "timeline": [{"time": "day 1 09:40", "text": 'release: Hal, saying: "Free to go"'}],
    "role": "The mayor's cousin", "accusation": "You accused Victor (right).",
    "side": ["Gives to Victor: 0."], "talks": [{"name": "Bob", "count": 2}],
})


def run(script):
    result = subprocess.run(["node", "-e", script], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_2d_reveal_close_and_reopen_survive_polling():
    run(DOM + DIALOG + JS + ENDING_JS + f"""
const pending = {{finished:true, accusation_pending:true, accusation_choices:[]}};
drawEnd(pending);
assert.equal($('end').open, undefined);
assert.equal($('accusation').hidden, false);
const state = {{finished:true, ending_scene:{SCENE}}};
drawEnd(state);
assert.equal($('end').open, true);
const content = text($('ending-content'));
for(const phrase of ['What really happened','What Hal did','You','Free to go',
  "The mayor's cousin",'Bob: 2 talks.']) assert.ok(content.includes(phrase));
$('close-ending').onclick(); drawEnd(state);
assert.equal($('end').hidden, true);
assert.equal($('end').open, false);
assert.equal($('view-ending').hidden, false);
$('view-ending').onclick(); drawEnd(state);
assert.equal($('end').open, true);
assert.equal($('end').opens, 2);
""")


def test_3d_accusation_then_reveal_and_no_reopening_on_poll():
    source = files("whisperwick").joinpath("web3d/ending.js").read_text()
    source = source.replace("import {renderEnding} from './ending-content.js';", "")
    source = source.replace("export class", "class")
    run(DOM + DIALOG + JS + source + f"""
const sent=[];
const ending = new Ending((path,body) => sent.push({{path,body}}));
ending.update({{finished:true, accusation_pending:true,
  accusation_choices:[{{id:'npc_bob',name:'Bob'}}]}});
assert.equal(ending.dialog.open,true);
assert.ok(!text(ending.dialog).includes('Victor killed'));
const select=ending.dialog.children.find(n => n.tag==='select');
select.value='npc_bob';
ending.dialog.children.find(n => n.tag==='button').onclick();
assert.deepEqual(sent,[{{path:'/accuse',body:{{target:'npc_bob'}}}}]);
const state={{finished:true, ending_scene:{SCENE}}};
ending.update(state);
assert.ok(text(ending.dialog).includes('Victor killed'));
assert.ok(document.body.classes.has('ending-scene'));
const buttons=ending.dialog.children.at(-1);
buttons.children[1].onclick(); ending.update(state);
assert.equal(ending.dialog.open,false);
assert.ok(!document.body.classes.has('ending-scene'));
ending.reopen.onclick();
assert.equal(ending.dialog.open,true);
assert.ok(document.body.classes.has('ending-scene'));
""")
