import {clothing} from './palette.js';

const $ = id => document.getElementById(id);
function el(tag,text) { const n = document.createElement(tag); n.textContent = text; return n; }
function stored(key,value) {
  // Private notes remain usable when browser storage is unavailable.
  try { if (value === undefined) return localStorage.getItem(key); localStorage.setItem(key,value); }
  catch {} return '';
}
export class Panels {
  constructor() {
    this.have = 0; this.notesKey = null;
    document.querySelectorAll('[data-panel]').forEach(button => button.onclick = () => {
      document.querySelectorAll('[data-panel]').forEach(b => {
        const selected = b === button;
        b.setAttribute('aria-pressed',String(selected)); $(b.dataset.panel).hidden = !selected;
      });
    });
    $('notes').oninput = () => { if (this.notesKey) stored(this.notesKey,$('notes').value); };
  }
  draw(s) {
    $('clock').textContent = s.clock; $('where').textContent = s.you.place.name;
    $('hook').textContent = s.hook;
    $('busy').textContent = s.waiting_on || s.turn_of ? 'Waiting on ' + (s.turn_of || s.waiting_on)
      : s.busy || (s.auto_wait ? 'Waiting for a reply...' : s.awaiting ? 'Your turn' : '');
    $('reject').textContent = s.rejection || '';
    $('end').textContent = [s.outcome,s.secret,s.error].filter(Boolean).join('\n');
    const feed = $('feed'), stick = feed.scrollTop + feed.clientHeight >= feed.scrollHeight-30;
    const start = s.feed_total-s.feed.length;
    s.feed.forEach((line,i) => {
      if (start+i < this.have) return;
      const details = el('details','');
      const summary=el('summary',line.length > 130 ? line.slice(0,130)+'…' : line);
      const dot=el('span',''); dot.className='speaker-dot'; dot.setAttribute('aria-hidden','true');
      // Match server-tagged speech exactly; never infer identity from a display name.
      const speaker=Object.entries(s.speech || {}).find(([,text]) => text===line)?.[0];
      if(speaker) dot.style.setProperty('--speaker','#'+clothing(speaker).toString(16).padStart(6,'0'));
      summary.prepend(dot); details.append(summary,el('p',line));
      feed.append(details);
    });
    this.have = Math.max(this.have,s.feed_total);
    if (stick) feed.scrollTop = feed.scrollHeight;
    const key = s.game_id ? 'whisperwick.notes.'+s.game_id : null;
    if (key !== this.notesKey) { this.notesKey = key; $('notes').value = key ? stored(key) || '' : ''; }
    const k = s.known; if (!k) return;
    const where = p => p.place.name + ', ' + p.clock;
    const sections = {
      People:[...k.people.map(p => p.name+', '+p.occupation+' — last seen '+where(p)+(p.held ? ' [held then]' : '')),
        ...k.bodies.map(p => p.name+' (body) — first seen '+where(p))],
      Places:k.places.map(p => p.name),
      Items:k.items.map(p => p.name+' — '+(p.carried ? 'you carry it' : p.place ? 'last seen '+where(p)
        : 'last carried at '+p.carried_place.name+', '+p.carried_clock))
    };
    $('known').replaceChildren();
    Object.entries(sections).forEach(([title,rows]) => {
      $('known').append(el('h2',title)); (rows.length ? rows : ['None yet.']).forEach(t => $('known').append(el('p',t)));
    });
  }
}
