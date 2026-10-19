"""Player-only start and ending controls for the 2D page."""

ROLE_HTML = """
<div class="card" id="role-picker" hidden>
  <h1>Choose your role</h1>
  <label for="role">Who are you?</label>
  <select id="role">
    <option value="">Wren, newcomer (original start)</option>
    <option value="cousin">The victim's cousin</option>
    <option value="peddler">Travelling peddler</option>
    <option value="partner">The killer's former partner</option>
  </select>
  <label for="crime-mode">Crime</label>
  <select id="crime-mode">
    <option value="random">Random crime</option>
    <option value="number">Enter a crime number</option>
  </select>
  <input id="crime-number" aria-label="Crime number" inputmode="numeric" hidden>
  <button id="start-game">Start the day</button><p id="start-error"></p>
</div>
"""

ENDING_HTML = """
<div class="card" id="accusation" hidden>
  <h2>Your accusation</h2>
  <p>Name one person, or nobody. This is your private record; villagers will never see it.</p>
  <select id="accused" aria-label="Your accusation"></select>
  <button id="record-accusation">Record and see the ending</button>
</div>
"""

ENDING_JS = """
function drawEnd(s) {
  $('bar').hidden = s.finished;
  $('end').hidden = !s.finished;
  drawAccusation(s);
  $('outcome').textContent = s.ending || s.outcome || '';
  $('secretbox').hidden = !s.secret;
  $('secret').textContent = s.secret || '';
  $('err').textContent = s.error || '';
}

// Inert keeps pointer and keyboard interaction inside the open guide.
function guide(open) {
  $('intro').hidden = !open;
  document.querySelectorAll('.page-head, .wrap').forEach(x => x.inert = open);
  document.body.classList.toggle('modal-open', open);
  (open ? $('close') : $('help')).focus({preventScroll: true});
}
$('close').onclick = $('dismiss').onclick = () => guide(false);
$('help').onclick = () => guide(true);
$('intro').onclick = e => { if (e.target === $('intro')) guide(false); };
// There are only two guide controls; wrap Tab in both directions.
document.addEventListener('keydown', e => {
  if ($('intro').hidden) return;
  if (e.key === 'Escape') { e.preventDefault(); guide(false); }
  if (e.key === 'Tab') {
    e.preventDefault();
    (document.activeElement === $('close') ? $('dismiss') : $('close')).focus();
  }
});
guide(true);

let picking = false;
function drawRolePicker(s) {
  const active = !!s.select_role;
  $('role-picker').hidden = !active;
  document.querySelectorAll('.page-head, .wrap').forEach(x => x.hidden = active);
  if (active && !picking) {
    guide(false);
    $('role').value = s.default_role || '';
    $('crime-mode').value = s.default_crime && s.default_crime !== 'random' ? 'number' : 'random';
    $('crime-number').value = s.default_crime === 'random' ? '' : s.default_crime || '';
    $('crime-number').hidden = $('crime-mode').value !== 'number';
    // Polling must leave keyboard focus with the player's current control.
    $('role').focus();
  }
  picking = active;
  return active;
}
$('crime-mode').onchange = () => {
  $('crime-number').hidden = $('crime-mode').value !== 'number';
};
$('start-game').onclick = async () => {
  $('start-game').disabled = true;
  try {
    const r = await fetch('/newgame', {method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({role: $('role').value || null,
        crime: $('crime-mode').value === 'number' ? $('crime-number').value : 'random'})});
    if (r.ok) location.reload();
    else $('start-error').textContent = (await r.json()).error;
  } catch (e) { $('start-error').textContent = 'Could not start the game.'; }
  $('start-game').disabled = false;
};
function drawAccusation(s) {
  $('accusation').hidden = !s.accusation_pending;
  $('end').hidden = !s.finished || !!s.accusation_pending;
  if (s.accusation_pending) fill($('accused'), s.accusation_choices, 'Nobody');
}
$('record-accusation').onclick = () => post('/accuse', {target: $('accused').value || null});
// New game returns to the picker. No world starts before the next role choice.
$('again').onclick = async () => {
  await fetch('/choose', {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: '{}'});
  location.reload();
};
"""
