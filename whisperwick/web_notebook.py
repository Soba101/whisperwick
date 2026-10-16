"""Private browser notes and visible sightings, inline in the same offline page.

Notes never enter a request. All sighting text uses textContent through el().
"""

NOTEBOOK = """
<div class="card" id="notebook">
  <div role="tablist" aria-label="Your notebook" class="notebook-tabs">
    <button id="known-tab" role="tab" aria-selected="true" aria-controls="known-panel">
      What you know</button>
    <button id="notes-tab" role="tab" aria-selected="false" aria-controls="notes-panel"
      tabindex="-1">Notes</button>
  </div>
  <div id="known-panel" role="tabpanel" aria-labelledby="known-tab" tabindex="0"></div>
  <div id="notes-panel" role="tabpanel" aria-labelledby="notes-tab" hidden>
    <label for="notes">Your notes</label>
    <textarea id="notes" rows="8" aria-describedby="notes-private"></textarea>
    <small id="notes-private">Only you can see these notes; the villagers cannot.</small>
  </div>
</div>
"""

NOTEBOOK_JS = """
let notesKey = null;
// Storage can be blocked or full; typing and switching tabs must still work.
function stored(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch (e) {}
  return null;
}
const notebookTabs = ['known', 'notes'];
function openNotebook(name, focus = false) {
  notebookTabs.forEach(n => {
    const selected = n === name, tab = $(n + '-tab');
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    $(n + '-panel').hidden = !selected;
    if (selected && focus) tab.focus();
  });
  stored('whisperwick.notebook-tab', name);
}
notebookTabs.forEach((name, index) => {
  $(name + '-tab').onclick = () => openNotebook(name);
  $(name + '-tab').onkeydown = e => {
    let next;
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') next = 1 - index;
    if (e.key === 'Home') next = 0;
    if (e.key === 'End') next = 1;
    if (next === undefined) return;
    e.preventDefault();
    openNotebook(notebookTabs[next], true);
  };
});
$('notes').oninput = () => { if (notesKey) stored(notesKey, $('notes').value); };
const savedTab = stored('whisperwick.notebook-tab');
openNotebook(savedTab === 'notes' ? 'notes' : 'known');
function sighting(row) { return row.place.name + ', ' + row.clock; }
function knownSection(title, rows) {
  const section = el('section', 'known-section');
  section.appendChild(el('h3', '', title));
  (rows.length ? rows : ['None yet.']).forEach(text =>
    section.appendChild(el('div', 'known-row', text)));
  return section;
}
function drawNotebook(s) {
  // A token digest keeps reloads in one game together and new games apart.
  const key = s.game_id ? 'whisperwick.notes.' + s.game_id : null;
  if (key !== notesKey) {
    notesKey = key;
    $('notes').value = key ? stored(key) || '' : '';
  }
  const k = s.known;
  if (!k) return;
  // Only being held is worth a word: free is the normal case.
  const people = k.people.map(p => p.name + ', ' + p.occupation
    + ' - last seen ' + sighting(p) + (p.held ? ' [held then]' : ''));
  // Bodies stay with People so the card needs only three short sections.
  people.push(...k.bodies.map(b => b.name + ' (body) - first seen ' + sighting(b)));
  const items = k.items.map(i => i.name + ' - ' + (i.carried ? 'you carry it'
    : i.place ? 'last seen on the ground ' + sighting(i)
    : 'last carried at ' + i.carried_place.name + ', ' + i.carried_clock));
  $('known-panel').replaceChildren(knownSection('People', people.sort()),
    knownSection('Places', k.places.map(p => p.name)), knownSection('Items', items));
}
// Initialize notes before polling can render a state.
loop();
"""
