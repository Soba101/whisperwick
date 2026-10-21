import {Controls} from './controls.js';
import {Panels} from './panels.js';
import {Ending} from './ending.js';
import {setupFeedback} from './feedback.js';
import {Voice} from './voice.js';
import {drawRole} from './role.js';

const fixture = new URLSearchParams(location.search).get('fixture') === '1';
const panels = new Panels();
let village = null, pending = false;
const controls = new Controls(post);
const voice = new Voice();
const openFeedback = setupFeedback('3d', fixture);
const ending = new Ending(post, openFeedback);
// A failed CDN or WebGL context still leaves the HUD and controls usable.
try {
  const {Village} = await import('./scene.js');
  village = new Village(hit => {
    if (hit.place) { village.follow = false; village.focus(hit.place); }
    controls.pick(hit);
  });
} catch (e) {
  document.getElementById('scene-error').textContent = '3D unavailable. Use the controls below or open the 2D view.';
}
document.getElementById('follow').onclick = () => {
  if (village) { village.endingShot=null; village.follow = true; }
};
async function post(path,body) {
  if (fixture) {
    document.getElementById('reject').textContent = 'Fixture preview: no actions are sent.'; return;
  }
  if (pending) return;
  pending = true;
  try {
    const r = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const result = await r.json();
    if (!r.ok) { document.getElementById('reject').textContent = result.error; return; }
    if (path === '/newgame') { location.reload(); return; }
    document.getElementById('message').value = '';
    await poll();
  } catch {
    document.getElementById('reject').textContent = 'Lost contact with the game. Please try again.';
  } finally { pending = false; }
}
async function poll() {
  const r = await fetch(fixture ? '/web3d/fixture_state.json' : '/state?since='+panels.have);
  if (!r.ok) throw new Error('State unavailable');
  const s = await r.json();
  if (s.gone) { location.reload(); return; }
  if (drawRole(s)) { await backdrop(); return; }  // no game yet: only the role card is live
  if (!s.you?.place) return;
  panels.draw(s); controls.update(s); voice.update(s); ending.update(s); village?.update(s);
  if (fixture) document.getElementById('busy').textContent = 'Fixture preview — no model or game actions';
}
// Behind the role card, draw the village's buildings from the packaged preview state.
// Places only: no people or items, so nothing about any crime shows before it starts.
async function backdrop() {
  if (!village || village.spots.size) return;
  const r = await fetch('/web3d/fixture_state.json');
  if (r.ok) village.build((await r.json()).places);
}
async function loop() {
  try { await poll(); }
  catch { document.getElementById('busy').textContent = 'Lost contact with the game...'; }
  if (!fixture) setTimeout(loop,700);
}
loop();
