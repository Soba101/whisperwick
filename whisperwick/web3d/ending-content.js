// Both pages render the same fixed facts. All game text stays plain text.
export function renderEnding(host, data) {
  const node=(tag,text) => {
    const n=document.createElement(tag); n.textContent=text; return n;
  };
  host.replaceChildren();
  const section=(title) => {
    const s=node('section',''); s.append(node('h2',title)); host.append(s); return s;
  };
  section('What really happened').append(node('p',data.account));
  const hal=section('What Hal did');
  data.custody.forEach(text => hal.append(node('p',text)));
  const timeline=node('ol',''); timeline.className='ending-timeline';
  data.timeline.forEach(e => {
    const row=node('li','');
    // event_line already contains the exact reason, without paraphrasing it.
    const prefix=e.text.indexOf('  ');
    row.append(node('time',e.time),node('p',prefix<0 ? e.text : e.text.slice(prefix+2)));
    timeline.append(row);
  });
  hal.append(timeline);
  if(!data.timeline.length) hal.append(node('p','No arrests or releases were recorded.'));
  const you=section('You');
  you.append(node('p',data.role),node('p',data.accusation),node('h3','Your side'));
  data.side.forEach(text => you.append(node('p',text)));
  if(!data.side.length) you.append(node('p','No interactions with a known killer to report.'));
  you.append(node('h3','People you talked to'));
  data.talks.forEach(p => you.append(node('p',`${p.name}: ${p.count} talk${p.count===1 ? '' : 's'}.`)));
  if(!data.talks.length) you.append(node('p','You did not talk to anyone.'));
}
