"""The play page script. Polls /state (fast while villagers act) and draws it.

Text goes in via textContent only.
"""

from importlib.resources import files

# Inline the shared picker so the 2D page still works without external scripts.
WHO_JS = files("whisperwick").joinpath("web3d/who.js").read_text().replace("export class", "class")

JS = WHO_JS + """
const $ = id => document.getElementById(id);
const who = new WhoPicker();
let have = 0, lastActions = '', mapBuilt = false, quiet = true, shown = null;

function el(tag, cls, text) {
  const x = document.createElement(tag);
  if (cls) x.className = cls;
  if (text !== undefined) x.textContent = text;
  return x;
}
function fill(sel, list, placeholder) {
  // Keep the player's choice across polls when it is still valid.
  const old = sel.value;
  sel.replaceChildren();
  if (placeholder) sel.appendChild(new Option(placeholder, ''));
  (list || []).forEach(o => sel.appendChild(new Option(o.name, o.id)));
  if ([...sel.options].some(o => o.value === old)) sel.value = old;
}
function buildMap(places) {
  places.forEach(p => {
    const box = el('div', 'place');
    box.id = 'p_' + p.id;
    box.style.left = p.x + '%'; box.style.top = p.y + '%';
    const title = el('b');
    const icon = el('span', 'icon', p.icon + ' ');
    icon.setAttribute('aria-hidden', 'true');
    title.appendChild(icon);
    title.appendChild(el('span', '', p.name));
    box.appendChild(title);
    box.appendChild(el('span', 'reach'));
    $('map').appendChild(box);
    p.links.forEach(q => {
      const o = places.find(z => z.id === q);
      if (o && p.id < q) {  // numbers only, so innerHTML is safe for the svg lines
        $('lines').innerHTML += '<line x1="' + p.x + '" y1="' + p.y
          + '" x2="' + o.x + '" y2="' + o.y + '"/>';
      }
    });
  });
  mapBuilt = true;
}
// People are drawn only at Wren's place: she cannot see anyone else.
function drawMap(y) {
  document.querySelectorAll('.place').forEach(b => {
    b.querySelectorAll('.tok').forEach(x => x.remove());
    const here = b.id === 'p_' + y.place.id;
    const canGo = y.exits.some(p => b.id === 'p_' + p.id);
    b.classList.toggle('here', here);
    b.classList.toggle('can-go', canGo);
    b.classList.toggle('distant', !here && !canGo);
    b.querySelector('.reach').textContent = here ? 'You are here' : canGo ? 'Can go' : '';
  });
  const box = $('p_' + y.place.id);
  box.appendChild(el('span', 'tok me', (y.name || 'Wren') + ' (you)'));
  y.people.forEach(p => box.appendChild(
    el('span', 'tok' + (p.held ? ' held' : ''), p.name + (p.held ? ' [held]' : ''))));
  y.bodies.forEach(b => box.appendChild(el('span', 'tok body', b.name + ' (body)')));
}
// empty = the word for an empty list: 'nobody' for people, 'nothing' for items.
function list(title, items, empty) {
  const d = el('div');
  d.appendChild(el('b', '', title + ': '));
  d.appendChild(el('span', '', items.length ? items.join(', ') : empty));
  return d;
}
function drawYou(y) {
  $('clock').textContent = y.clock;
  $('where').textContent = y.place.name;
  $('you').replaceChildren(
    list('You', [(y.name || 'Wren') + ', ' + (y.title || y.occupation || 'newcomer')]),
    list('People here', y.people.map(p => p.name + ' (' + p.occupation + ')'
      + (p.held ? ' [held]' : '')), 'nobody'),
    list('Bodies here', y.bodies.map(b => b.name), 'none'),
    list('On the ground', y.ground.map(i => i.name), 'nothing'),
    list('You carry', y.carried.map(i => i.name), 'nothing'),
    list('Exits', y.exits.map(e => e.name), 'none'));
}
function drawFeed(s) {
  const ul = $('feed'), stick = ul.scrollTop + ul.clientHeight >= ul.scrollHeight - 30;
  // Two polls can be in flight at once (Send also polls), and both bring the same new lines.
  // The answer's lines start at feed_total - feed.length; skip any line already on the page.
  const start = s.feed_total - s.feed.length;
  s.feed.forEach((t, i) => { if (start + i >= have) ul.appendChild(el('li', '', t)); });
  have = Math.max(have, s.feed_total);
  if (stick) ul.scrollTop = ul.scrollHeight;
}
// Only the fields the chosen action needs are shown.
function drawFields() {
  const a = JSON.parse(lastActions || '[]').find(x => x.action === $('action').value);
  $('target').hidden = !a || a.targets === null;
  $('item').hidden = !a || a.items === null;
  $('message').hidden = !a || !a.message;
  if (!a) return;
  if (a.targets !== null) fill($('target'), a.targets, a.target_required ? '' : 'everyone here');
  if (a.items !== null) fill($('item'), a.items);
  who.apply($('target')); drawTalkTo();
}
// Say plainly who a message goes to: the who-menu keeps its last choice between turns.
function drawTalkTo() {
  const t = $('target'), on = $('action').value === 'talk' && !t.hidden && t.value;
  const name = on ? t.options[t.selectedIndex].text : '';
  $('talkto').hidden = !on;
  $('talkto').textContent = on ? 'You are talking to ' + name : '';
  $('message').placeholder = on ? 'Say something to ' + name + '...' : 'What do you say?';
}
function drawBar(s) {
  if (who.sync(s, $('target'))) lastActions = '';
  const text = JSON.stringify(s.actions);
  if (text !== lastActions) {
    lastActions = text;
    const old = $('action').value;
    $('action').replaceChildren();
    s.actions.forEach(a => {
      const option = el('option', '', a.icon + ' ' + a.label + (a.reason ? ' — ' + a.reason : ''));
      option.value = a.action;
      option.disabled = !!a.reason;
      $('action').appendChild(option);
    });
    const chosen = s.actions.find(a => a.action === old && !a.reason)
      || s.actions.find(a => !a.reason);
    if (chosen) $('action').value = chosen.action;
    drawFields();
  }
  who.apply($('target')); drawTalkTo();
  const off = !s.awaiting;
  ['action', 'target', 'item', 'message', 'send', 'w10', 'w60'].forEach(i => $(i).disabled = off);
  $('quit').disabled = s.finished;
  $('busy').hidden = s.awaiting || s.finished;
  // The server says who is busy, but only in words that fit what Wren can see.
  $('busy').textContent = s.busy || 'The villagers are acting...';
  drawHint(s);
  $('reject').hidden = !s.rejection;
  $('reject').textContent = s.rejection ? 'You cannot do that: ' + s.rejection : '';
}
// One plain line above the bar. HINTS comes from web_guide.py. A refusal has its own line.
function drawHint(s) {
  shown = s;
  const a = JSON.parse(lastActions || '[]').find(x => x.action === $('action').value);
  const needsText = s.awaiting && a && a.message && !$('message').value.trim();
  $('hint').textContent = s.auto_wait ? HINTS.auto : !s.awaiting ? HINTS.busy
    : needsText ? HINTS.message : HINTS.turn;
}
function render(s) {
  if (s.gone) { location.reload(); return; }  // the game was stopped or is unknown here
  if (drawRolePicker(s)) return;
  $('crime-label').textContent = s.crime_seed == null ? '' : 'Crime #' + s.crime_seed;
  $('hook').textContent = s.hook;
  if (s.crime_seed != null) $('goal').textContent =
    "Find out who killed the victim before nightfall, or don't: it's your day.";
  document.querySelectorAll('.hook').forEach(x => x.textContent = s.hook);
  drawNotebook(s);
  quiet = s.awaiting || s.finished;
  if (!s.you.place) return;  // the game has not started yet
  if (!mapBuilt) {
    buildMap(s.places);
  }
  drawYou(s.you); drawMap(s.you); drawFeed(s); drawBar(s); drawEnd(s);
}
async function poll() {
  try {
    render(await (await fetch('/state?since=' + have)).json());
  } catch (e) {
    $('busy').hidden = false;
    $('busy').textContent = 'Lost contact with the game...';
  }
}
async function post(path, body) {
  const r = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body || {})});
  if (!r.ok) $('reject').textContent = (await r.json()).error;
  poll();
}
// Redraw the hint at once when the choice or the typed text changes.
$('action').onchange = () => { drawFields(); if (shown) drawHint(shown); };
$('message').oninput = () => { if (shown) drawHint(shown); };
$('target').onchange = () => { who.choose($('target').value); drawTalkTo(); };
$('send').onclick = () => post('/act', {action: $('action').value,
  target: $('target').hidden ? null : $('target').value,
  item: $('item').hidden ? null : $('item').value,
  message: $('message').hidden ? null : $('message').value}).then(() => $('message').value = '');
$('message').onkeydown = e => { if (e.key === 'Enter') $('send').click(); };
$('w10').onclick = () => post('/wait', {minutes: 10});
$('w60').onclick = () => post('/wait', {minutes: 60});
$('quit').onclick = () => { if (confirm('Leave the game?')) post('/quit'); };
// Slow polling while it is Wren's turn, quick while villagers act, so lines appear at once.
async function loop() {
  await poll();
  setTimeout(loop, quiet ? 1000 : 500);
}
// The notebook initializes before the first poll.
"""
