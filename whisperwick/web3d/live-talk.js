// Live words are separate from the committed feed and disappear on the next poll.
export function drawLiveTalk(state,node) {
  node.replaceChildren();
  Object.values(state.live_talk || {}).forEach(line => {
    const row=document.createElement('p'), label=document.createElement('strong');
    label.textContent=line.name+' is speaking...';
    const words=document.createElement('div'); words.textContent=line.message;
    row.append(label,words); node.append(row);
  });
}
