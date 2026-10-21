// Week 17: pick a role over the 3D village, so new players never land on the 2D page first.
// The card is the same markup as the 2D picker and posts the same body to /newgame.
const $ = id => document.getElementById(id);
let picking = false;

// Returns true while the server says no game exists yet (it answers select_role).
export function drawRole(s) {
  const card = $('role-picker');
  if (!card) return false;  // fixture preview: the page has no card
  const active = !!s.select_role;
  card.hidden = !active;
  // The village behind stays visible but cannot be used until a game exists.
  document.querySelectorAll('header, main, footer').forEach(x => x.inert = active);
  if (active && !picking) {
    // Fill the server's defaults once; polling must not undo the player's choices.
    $('role').value = s.default_role || '';
    $('crime-mode').value = s.default_crime && s.default_crime !== 'random' ? 'number' : 'random';
    $('crime-number').value = s.default_crime === 'random' ? '' : s.default_crime || '';
    $('crime-number').hidden = $('crime-mode').value !== 'number';
    $('role').focus();
  }
  picking = active;
  return active;
}

if ($('role-picker')) {
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
      // A reload loads the village with the new game; the card no longer shows.
      if (r.ok) { location.reload(); return; }
      $('start-error').textContent = (await r.json()).error;
    } catch { $('start-error').textContent = 'Could not start the game.'; }
    $('start-game').disabled = false;
  };
}
