const assert = require('node:assert/strict');
// A small DOM surface runs the real controls without an HTTP server.
class Element {
  constructor() {
    this.children = []; this.hidden = false; this.parentElement = {}; this._value = null;
  }
  get options() { return this.children; }
  get value() { return this._value ?? this.children[0]?.value ?? ''; }
  set value(value) { this._value = value; }
  get selectedIndex() { return this.children.findIndex(o => o.value === this.value); }
  append(...xs) { this.children.push(...xs); }
  appendChild(x) { this.append(x); }
  replaceChildren(...xs) { this.children = xs; this._value = null; }
  setAttribute() {}
  focus() {}
}
const elements = new Map();
const document = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  },
  createElement() { return new Element(); }
};
class Option {
  constructor(text, value) { this.text = text; this.value = value; }
}
const HINTS = {}, requests = [];
const fetch = async (path, options) => {
  requests.push({path, body:JSON.parse(options.body || '{}')});
  return {ok:true, json:async () => ({})};
};
// INSERT CONTROLS HERE
const controls = view === '3d' ? new Controls((path, body) => requests.push({path, body})) : null;
const update = s => controls ? controls.update(s) : drawBar(s);
const chooseTalk = () => {
  if (controls) controls.choose('talk');
  else { $('action').value = 'talk'; drawFields(); }
};
const pick = id => { $('target').value = id; $('target').onchange(); };
update(state); chooseTalk();
assert.equal($('target').value, 'npc_bob');
state.reply_to = {id:'npc_victor', sequence:2}; update(state);
assert.equal($('target').value, 'npc_victor');
// Polling the same speech must preserve a deliberate manual selection.
pick('npc_bob'); update(state);
assert.equal($('target').value, 'npc_bob');
state.reply_to = {id:'npc_victor', sequence:3}; update(state);
assert.equal($('target').value, 'npc_victor');
state.reply_to = null; state.you.place.id = 'loc_inn'; update(state);
assert.equal($('target').value, 'npc_bob');
// Clicking a person also works while villagers are acting.
if (controls) {
  state.awaiting = false; update(state);
  controls.pick({person:'npc_victor'});
  assert.equal($('target').value, 'npc_victor');
  update(state); assert.equal($('target').value, 'npc_victor');
  state.awaiting = true; update(state);
  controls.choose('give'); controls.pick({person:'npc_bob'});
  assert.equal(controls.action, 'give');
  assert.equal($('target').value, 'npc_bob');
}
const use = state.actions.find(a => a.action === 'use');
assert.equal(use.reason, 'that cannot be used up');
if (controls) assert.equal($('actions').children.find(b => b.textContent.endsWith('Use')).disabled, true);
else assert.equal($('action').options.find(o => o.value === 'use').disabled, true);
use.reason = null; use.items = [{id:'item_tea', name:'cup of tea', consumable:true}];
update(state);
if (controls) controls.choose('use');
else { $('action').value = 'use'; drawFields(); }
assert.equal($('item').value, 'item_tea');
assert.equal(controls ? $('target').parentElement.hidden : $('target').hidden, true);

if (controls) $('command').onsubmit({preventDefault() {}});
else $('send').onclick();
assert.deepEqual(requests[0], {path:'/act', body:{action:'use', target:null,
  item:'item_tea', message:null}});
