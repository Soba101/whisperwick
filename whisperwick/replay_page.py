"""The replay page: one HTML file, inline CSS and JS, no external anything.

It opens offline. All text from the run is put in with textContent (never innerHTML),
and the embedded JSON is escaped in replay_data.to_json.
"""

from html import escape

from whisperwick.replay_data import to_json
from whisperwick.replay_layout import BODY, CSS

JS = """
const D = JSON.parse(document.getElementById('run').textContent);
const $ = id => document.getElementById(id);
const nm = id => D.names[id] || id;
const WINDOW = 120;  // the feed shows this many game minutes back from now
let now = D.start, timer = null;

function clockLabel(t) {
  const m = t % 1440;
  return 'day ' + (Math.floor(t / 1440) + 1) + ' ' + String(Math.floor(m / 60)).padStart(2, '0')
    + ':' + String(m % 60).padStart(2, '0');
}
// Same rules as replay_state.py: moves change places, arrests and releases change custody.
function stateAt(t) {
  const pos = {}, held = {};
  D.people.forEach(p => pos[p.id] = p.loc);
  for (const e of D.events) {
    if (e.tick > t) break;
    if (e.type === 'move') pos[e.actor] = e.to;
    (e.moves || []).forEach(to => pos[e.actor] = to);
    if (e.type === 'arrest') held[e.to] = e.actor;
    if (e.type === 'release') delete held[e.to];
  }
  return {pos, held};
}
function el(tag, cls, text) {
  const x = document.createElement(tag);
  if (cls) x.className = cls;
  if (text !== undefined) x.textContent = text;
  return x;
}
function line(e) {
  const who = nm(e.actor), to = e.to ? nm(e.to) : 'everyone';
  if (e.type === 'gesture' || e.moves) return e.text;
  if (e.type === 'talk') return who + ' -> ' + to + ': ' + e.text;
  if (e.type === 'move') return who + ' walks to ' + to;
  if (e.type === 'arrest') return who + ' arrests ' + to + (e.text ? ': ' + e.text : '');
  if (e.type === 'release') return who + ' releases ' + to + (e.text ? ': ' + e.text : '');
  return who + ' ' + e.type + 's the ' + e.item + (e.type === 'drop' ? '' : ' (' + to + ')');
}
function drawMap(s) {
  D.places.forEach(p => {
    const box = $('p_' + p.id);
    box.querySelectorAll('.tok').forEach(x => x.remove());
    D.people.forEach(w => {
      if (s.pos[w.id] !== p.id) return;
      const held = s.held[w.id];
      const tok = el('span', 'tok' + (w.alive ? '' : ' body') + (held ? ' held' : ''),
        w.name[0] + ' ' + w.name + (w.alive ? '' : ' (body)') + (held ? ' [held]' : ''));
      box.appendChild(tok);
    });
  });
}
function drawFeed() {
  const inWindow = x => x.tick <= now && x.tick > now - WINDOW;
  const rows = D.events.filter(inWindow).map(e => ({e, t: e.tick}));
  if ($('thoughts').checked) {
    D.thoughts.filter(inWindow)
      .forEach(x => rows.push({th: x, t: x.tick}));
    rows.sort((a, b) => a.t - b.t);
  }
  const ul = $('feed');
  ul.replaceChildren();
  rows.slice(-40).forEach(r => {
    const li = el('li', r.th ? 'thought' : r.e.type);
    li.appendChild(el('span', 't', clockLabel(r.t).slice(6)));
    if (r.th) li.appendChild(el('span', '', nm(r.th.npc) + ' (private thought): ' + r.th.text));
    else {
      li.appendChild(el('span', '', line(r.e)));
      if (r.e.claim) li.appendChild(el('span', 'tag', ' [claim: ' + r.e.claim + ']'));
    }
    ul.appendChild(li);
  });
  ul.scrollTop = ul.scrollHeight;
}
function draw() {
  $('clock').textContent = clockLabel(now);
  $('slider').value = now;
  drawMap(stateAt(now));
  drawFeed();
}
function stop() { clearInterval(timer); timer = null; $('play').textContent = 'Play'; }
function play() {
  if (timer) return stop();
  if (now >= D.end) now = D.start;
  $('play').textContent = 'Pause';
  // Ten frames a second; the speed is game minutes per real second.
  timer = setInterval(() => {
    now = Math.min(D.end, now + Number($('speed').value) / 10);
    if (now >= D.end) stop();
    draw();
  }, 100);
}
function step(dir) {
  stop();
  const ticks = D.events.map(e => e.tick);
  const next = dir > 0 ? ticks.find(t => t > now) : ticks.filter(t => t < now).pop();
  if (next !== undefined) now = next;
  draw();
}
function build() {
  $('title').textContent = 'Replay: ' + (D.label || 'run');
  D.places.forEach(p => {
    const box = el('div', 'place');
    box.id = 'p_' + p.id;
    box.style.left = p.x + '%'; box.style.top = p.y + '%';
    box.appendChild(el('b', '', p.name));
    $('map').appendChild(box);
    // Lines: numbers only, so innerHTML is safe here (it parses as SVG inside an svg tag).
    p.links.forEach(q => {
      const o = D.places.find(z => z.id === q);
      if (o && p.id < q) {
        $('lines').innerHTML += '<line x1="' + p.x + '" y1="' + p.y
          + '" x2="' + o.x + '" y2="' + o.y + '"/>';
      }
    });
  });
  $('slider').min = D.start; $('slider').max = D.end;
  $('slider').oninput = e => { stop(); now = Number(e.target.value); draw(); };
  $('play').onclick = play;
  $('next').onclick = () => step(1);
  $('prev').onclick = () => step(-1);
  $('thoughts').onchange = drawFeed;
  $('thoughtbox').hidden = D.thoughts.length === 0;
  draw();
}
build();
"""



def render_page(data: dict) -> str:
    """The whole file as one string. The JSON goes in last, after all other replacing."""
    title = escape(f"Replay: {data['label'] or 'run'}")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title><style>{CSS}</style></head><body>{BODY}"
        f'<script type="application/json" id="run">{to_json(data)}</script>'
        f"<script>{JS}</script></body></html>"
    )
