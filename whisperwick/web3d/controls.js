const $ = id => document.getElementById(id);

export class Controls {
  constructor(post) {
    this.post = post; this.action = 'look'; this.signature = '';
    $('command').onsubmit = e => {
      e.preventDefault();
      const a = this.state.actions.find(a => a.action === this.action);
      if (!a) return;
      post('/act', {action:a.action, target:a.targets === null ? null : $('target').value,
        item:a.items === null ? null : $('item').value,
        message:a.message ? $('message').value : null});
    };
    $('w10').onclick = () => post('/wait', {minutes:10});
    $('w60').onclick = () => post('/wait', {minutes:60});
    $('quit').onclick = () => post('/quit', {});
    $('again').onclick = () => post('/newgame', {});
  }
  choose(action, target) {
    const a = this.state?.actions.find(a => a.action === action);
    if (!a || a.reason || !this.state.awaiting) return;
    this.action = action; this.signature = ''; this.update(this.state);
    if (target) $('target').value = target;
    if (a.message) $('message').focus();
  }
  pick(hit) {
    const s = this.state;
    if (!s) return;
    if (hit.place) {
      // Membership is supplied by the server, never inferred from map geometry.
      const a = s.actions.find(a => a.action === 'move');
      if (s.awaiting && !a?.reason && a?.targets.some(t => t.id === hit.place))
        this.post('/act', {action:'move', target:hit.place});
    } else if (hit.item) {
      this.choose('take'); $('item').value = hit.person;
    } else {
      const person = [s.player, ...s.you.people].find(p => p.id === hit.person);
      if (!person) return;
      $('inspect').textContent = person.id === s.player.id
        ? 'You carry: ' + (s.you.carried.map(i => i.name).join(', ') || 'nothing')
        : person.name + (person.held ? ' [held]. ' : '. ') + 'Carried items are private.';
      // Keep Give and Show selected when a person is clicked.
      const chosen = s.actions.find(a => a.action === this.action);
      this.choose(chosen?.targets?.some(t => t.id === person.id) ? this.action : 'talk', person.id);
    }
  }
  update(s) {
    this.state = s;
    const signature = JSON.stringify([s.actions, s.awaiting, this.action]);
    if (signature !== this.signature) {
      this.signature = signature; $('actions').replaceChildren();
      s.actions.forEach(a => {
        const b = document.createElement('button'); b.textContent = a.icon + ' ' + a.label;
        b.disabled = !!a.reason || !s.awaiting; b.title = a.reason || (!s.awaiting ? 'Waiting for the server to request your action.' : a.label);
        b.setAttribute('aria-pressed', String(this.action === a.action));
        b.onclick = () => this.choose(a.action); $('actions').append(b);
      });
      const a = s.actions.find(a => a.action === this.action);
      if (a) {
        this.fill('target',a.targets, !a.target_required);
        this.fill('item',a.items,false);
        $('message').parentElement.hidden = !a.message;
        $('send').disabled = !s.awaiting || !!a.reason;
      }
    }
    ['target','item','message','w10','w60'].forEach(id => $(id).disabled = !s.awaiting);
    $('message').maxLength = s.message_limit;
    $('quit').disabled = s.finished; $('again').hidden = !s.finished;
    $('command').hidden = s.finished;
  }
  fill(id, choices, optional) {
    const select = $(id), old = select.value;
    select.parentElement.hidden = choices === null; select.replaceChildren();
    if (optional) select.append(new Option('Everyone here', ''));
    (choices || []).forEach(c => select.append(new Option(c.name,c.id)));
    if ([...select.options].some(o => o.value === old)) select.value = old;
  }
}
