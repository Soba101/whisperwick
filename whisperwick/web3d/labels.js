export class Labels {
  constructor(pick) { this.pick=pick; this.rows=[]; }
  add(text,position,pick,kind='person') {
    const node=document.createElement('button'); node.className='label '+kind;
    const name=document.createElement('span'); name.textContent=text; node.append(name);
    node.onclick=() => this.pick(pick); document.getElementById('labels').append(node);
    const row={node,name,position,kind}; this.rows.push(row); return row;
  }
  remove(row) { row.node.remove(); this.rows.splice(this.rows.indexOf(row),1); }
  speech(row,text) {
    if (text===row.said) return;
    row.said=text; row.until=performance.now()+6500;
    row.node.querySelector('small')?.remove();
    if (!text) return;
    // Speech metadata contains the feed line. Keep only its quoted words.
    const first=text.indexOf('"'), last=text.lastIndexOf('"');
    text=first>=0 && last>first ? text.slice(first+1,last) : text;
    const bubble=document.createElement('small'); bubble.className='bubble';
    bubble.textContent=text.length>80 ? text.slice(0,79)+'…' : text;
    bubble.title=text; row.node.append(bubble);
  }
  draw(camera,width,height,now) {
    const occupied=[];
    // Place labels get the first clear slots. Remaining names stack vertically.
    const priority={place:0,person:1,item:2};
    const ordered=[...this.rows].sort((a,b) => priority[a.kind]-priority[b.kind]);
    ordered.forEach(row => {
      const {node}=row, v=row.position.clone().project(camera);
      const bubble=node.querySelector('small');
      if (bubble) { bubble.style.opacity=String(Math.min(1,Math.max(0,(row.until-now)/1200))); if(now>row.until) bubble.remove(); }
      node.hidden=!!row.invisible || v.z>1 || v.z< -1 || Math.abs(v.x)>1.1 || Math.abs(v.y)>1.1;
      if(node.hidden) return;
      const w=node.offsetWidth,h=node.offsetHeight, anchor=(1-v.y)*height/2;
      const x=Math.max(4,Math.min(width-w-4,(v.x+1)*width/2-w/2));
      let chosen=null;
      for(let i=0;i<240;i++) {
        const slot=Math.floor(i/3), offset=slot===0 ? 0 : Math.ceil(slot/2)*(h+5)*(slot%2 ? -1 : 1);
        const shift=[0,-1,1][i%3]*Math.ceil(slot/8)*(w+5);
        const left=Math.max(4,Math.min(width-w-4,x+shift));
        const y=Math.max(52,Math.min(height-h-4,anchor-h+offset));
        const r={x:left,y,w,h};
        if(!occupied.some(b => left<b.x+b.w+4 && left+w+4>b.x && y<b.y+b.h+4 && y+h+4>b.y)) { chosen=r; break; }
      }
      node.hidden=!chosen;
      if(chosen) { occupied.push(chosen); node.style.transform=`translate(${chosen.x}px,${chosen.y}px)`; }
    });
  }
}
