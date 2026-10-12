"""The play page script. Polls /state (fast while villagers act) and draws it.

Text goes in via textContent only.
"""

JS = """
const $ = id => document.getElementById(id);
let have = 0, intro = false, lastActions = '', mapBuilt = false, quiet = true;

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
    box.appendChild(el('b', '', p.name));
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
    b.classList.toggle('here', b.id === 'p_' + y.place.id);
  });
  const box = $('p_' + y.place.id);
  box.appendChild(el('span', 'tok me', 'Wren (you)'));
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
    list('People here', y.people.map(p => p.name + ' (' + p.occupation + ')'
      + (p.held ? ' [held]' : '')), 'nobody'),
    list('Bodies here', y.bodies.map(b => b.name), 'none'),
    list('On the ground', y.ground.map(i => i.name), 'nothing'),
    list('You carry', y.carried.map(i => i.name), 'nothing'),
    list('Exits', y.exits.map(e => e.name), 'none'));
}
function drawFeed(s) {
  const ul = $('feed'), stick = ul.scrollTop + ul.clientHeight >= ul.scrollHeight - 30;
  s.feed.forEach(t => ul.appendChild(el('li', '', t)));
  have = s.feed_total;
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
}
function drawBar(s) {
  const text = JSON.stringify(s.actions);
  if (text !== lastActions) {
    lastActions = text;
    const old = $('action').value;
    $('action').replaceChildren();
    s.actions.forEach(a => $('action').appendChild(new Option(a.label, a.action)));
    if (s.actions.some(a => a.action === old)) $('action').value = old;
    drawFields();
  }
  const off = !s.awaiting;
  ['action', 'target', 'item', 'message', 'send', 'w10', 'w60'].forEach(i => $(i).disabled = off);
  $('quit').disabled = s.finished;
  $('busy').hidden = s.awaiting || s.finished;
  // The server says who is busy, but only in words that fit what Wren can see.
  $('busy').textContent = s.busy || 'The villagers are acting...';
  $('reject').hidden = !s.rejection;
  $('reject').textContent = s.rejection ? 'You cannot do that: ' + s.rejection : '';
}
function drawEnd(s) {
  $('bar').hidden = s.finished;
  $('end').hidden = !s.finished;
  $('outcome').textContent = s.outcome || '';
  $('secretbox').hidden = !s.secret;
  $('secret').textContent = s.secret || '';
  $('err').textContent = s.error || '';
}
function render(s) {
  if (s.gone) { location.reload(); return; }  // the game was stopped or is unknown here
  quiet = s.awaiting || s.finished;
  if (!s.you.place) return;  // the game has not started yet
  if (!mapBuilt) {
    buildMap(s.places);
    $('start').textContent = 'It is ' + s.you.clock + ', at the ' + s.you.place.name + '.';
    $('intro').hidden = intro;
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
$('action').onchange = drawFields;
$('send').onclick = () => post('/act', {action: $('action').value,
  target: $('target').hidden ? null : $('target').value,
  item: $('item').hidden ? null : $('item').value,
  message: $('message').hidden ? null : $('message').value}).then(() => $('message').value = '');
$('message').onkeydown = e => { if (e.key === 'Enter') $('send').click(); };
$('w10').onclick = () => post('/wait', {minutes: 10});
$('w60').onclick = () => post('/wait', {minutes: 60});
$('quit').onclick = () => { if (confirm('Leave the game?')) post('/quit'); };
$('close').onclick = () => { intro = true; $('intro').hidden = true; };
$('help').onclick = () => { $('intro').hidden = !$('intro').hidden; };
$('again').onclick = async () => {
  const r = await fetch('/newgame', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: '{}'});
  if (r.ok) location.reload(); else $('err').textContent = (await r.json()).error;
};
// Slow polling while it is Wren's turn, quick while villagers act, so lines appear at once.
async function loop() {
  await poll();
  setTimeout(loop, quiet ? 1000 : 500);
}
loop();
"""
