import * as THREE from 'three';
import {pose} from './model-characters.js';
import {dispose} from './models.js';
import {character,tint} from './characters.js';
import {item} from './items.js';
import {hash,clothing} from './geometry.js';

export class Figures {
  constructor(village) { this.v=village; this.rows=new Map(); this.seen=new Map(); this.interactions=new Map(); }
  update(s) {
    const rows=[{...s.player,carried:s.you.carried},...s.you.people.map(p => ({...p})),
      ...s.you.bodies.map(p => ({...p,body:true})),...s.you.ground.map(p => ({...p,item:true}))];
    const now=performance.now();
    (s.motions || []).forEach(m => {
      if(this.seen.get(m.id)===m.sequence) return;
      this.seen.set(m.id,m.sequence);
      if(!this.started) return;
      const row=rows.find(p => p.id===m.id);
      if(row) row.motion=m;
      // Only a newly witnessed departure gets a short animation outside the current view.
      else if(this.rows.has(m.id)) rows.push({...m,motion:m,expires:now+1200});
    });
    for(const [id,r] of this.rows) {
      if(r.expires>now && !rows.some(p => p.id===id)) rows.push({...r.record,expires:r.expires});
    }
    this.started=true;
    const visible=new Set(rows.map(p => p.id));
    // Forget unseen figures immediately; remembered sightings are only in the notebook.
    for(const [id,r] of this.rows) if(!visible.has(id)) {
      this.v.scene.remove(r.group); this.v.labels.remove(r.label);
      dispose(r.group); this.rows.delete(id);
      if(this.player===r) this.player=null;
    }
    const sorted=[...rows].sort((a,b) => a.id.localeCompare(b.id));
    sorted.forEach(p => {
      const place=p.motion?.to || p.place || s.you.place.id;
      const spot=this.v.spots.get(place); if(!spot) return;
      let r=this.rows.get(p.id);
      if(!r) {
        const group=p.item ? item(p) : character(p,p.id===s.player.id);
        this.v.scene.add(group);
        const label=this.v.labels.add(p.name,new THREE.Vector3(),{person:p.id,item:p.item},p.item ? 'item' : 'person');
        if(!p.item) {
          label.node.style.setProperty('--person-color','#'+clothing(p.id).toString(16).padStart(6,'0'));
          label.node.classList.toggle('player',p.id===s.player.id);
        }
        r={group,label,place:null,phase:hash(p.id)%100}; this.rows.set(p.id,r);
      }
      const peers=sorted.filter(q => (q.motion?.to || q.place || s.you.place.id)===place && !!q.item===!!p.item && !q.held);
      const index=peers.findIndex(q => q.id===p.id);
      // Local +z faces the island centre, so the arc cannot spill over the rim.
      const count=peers.length, rank=Math.max(0,index), perRow=p.item ? 8 : 6;
      const row=Math.floor(rank/perRow), slots=Math.min(perRow,count-row*perRow);
      const angle=slots<=1 ? 0 : (rank%perRow-(slots-1)/2)*Math.min(.42,1.8/(slots-1));
      const distance=(p.item ? 5.4 : 7)+row*2;
      const target=this.v.local(place,Math.sin(angle)*distance,.2,Math.cos(angle)*distance);
      // Very crowded scenarios still keep every public figure on solid ground.
      const limit=this.v.island-2, radial=Math.hypot(target.x,target.z);
      if(radial>limit) { target.x*=limit/radial; target.z*=limit/radial; }
      if(p.held && place==='loc_town_hall') target.copy(this.v.local(place,2.3,.2,2.4));
      // Tween only consecutive observed placements; never infer an unseen route.
      r.record=p; r.expires=p.expires;
      const changed=r.place!==place || p.motion;
      if(changed) {
        const from=p.motion?.from || r.place;
        r.start=r.place && this.v.links.get(from)?.includes(place) ? r.group.position.clone() : target.clone();
        r.curve=this.v.curves.get([from,place].sort().join('|'));
        r.reverse=from>place; r.time=now; r.place=place;
        if(p.motion && r.curve) r.start=this.v.entrance(from);
        r.target=target;
        delete p.motion;
      } else r.target.copy(target);
      const interaction=(s.interactions || []).find(e => e.id===p.id);
      if(interaction && this.interactions.get(p.id)!==interaction.sequence) {
        this.interactions.set(p.id,interaction.sequence);
        if(this.hadSnapshot) r.interactUntil=now+1100;
      }
      p.place=place;
      r.waiting=p.waiting || p.sleeping || (p.id===s.player.id && s.auto_wait);
      if(!p.item) tint(r.group,p.held || p.body);
      r.group.rotation.z=p.body ? Math.PI/2 : 0;
      r.label.name.textContent=p.name+(p.held ? ' [held]' : p.body ? ' (body)' : '');
      r.label.node.title=p.carried ? 'Carrying: '+(p.carried.map(x => x.name).join(', ') || 'nothing')
        : p.item ? p.name : 'Carried items are private.';
      this.v.labels.speech(r.label,s.speech?.[p.id]);
      if(p.id===s.player.id) this.player=r;
    });
    this.hadSnapshot=true;
  }
  animate(now) {
    const dt=Math.min(.05,(now-(this.last || now))/1000); this.last=now;
    this.rows.forEach(r => {
      const p=r.record;
      r.group.visible=!r.expires || r.expires>now; r.label.invisible=!r.group.visible;
      const t=Math.min(1,(now-r.time)/1200), ease=t*t*(3-2*t);
      const before=r.group.position.clone();
      r.group.position.lerpVectors(r.start,r.target,ease);
      if(r.curve && t<1 && r.start.distanceTo(r.target)>4) {
        const u=r.reverse ? 1-ease : ease;
        const path=r.curve.getPoint(u), first=r.curve.getPoint(r.reverse ? 1 : 0), last=r.curve.getPoint(r.reverse ? 0 : 1);
        path.add(r.start.clone().sub(first).multiplyScalar(1-ease));
        path.add(r.target.clone().sub(last).multiplyScalar(ease)); r.group.position.copy(path);
      }
      const walking=t<1 && r.start.distanceTo(r.target)>.5;
      if(!p.item) {
        const animation=p.held || p.body ? 'idle' : walking ? 'walk' :
          r.interactUntil>now ? 'interact-right' : r.waiting ? 'sit' : 'idle';
        pose(r.group,animation,dt);
        // A replacement may finish between polls, so apply public tint each frame.
        tint(r.group,p.held || p.body);
      }
      if(!p.item && !p.body && !p.held) {
        r.group.position.y+=walking ? Math.abs(Math.sin(t*Math.PI*7))*.16 : Math.sin(now*.002+r.phase)*.035;
        const delta=r.group.position.clone().sub(before);
        if(walking && Math.hypot(delta.x,delta.z)>.001) r.group.rotation.y=Math.atan2(delta.x,delta.z);
        else r.group.rotation.y=Math.atan2(this.v.camera.position.x-r.group.position.x,
          this.v.camera.position.z-r.group.position.z);
        if(!walking && r.label.until>now && r.label.said) {
          // Facing a visible neighbour is cosmetic, not a guess about a hidden recipient.
          const other=[...this.rows.values()].find(q => q!==r && !q.record.item && q.place===r.place);
          if(other) r.group.rotation.y=Math.atan2(other.target.x-r.target.x,other.target.z-r.target.z);
        }
      }
      if(r.group.userData.glow) r.group.userData.glow.intensity=.7+Math.sin(now*.007+r.phase)*.12;
      r.label.position.copy(r.group.position).y+=p.item ? .75 : 3.85;
    });
  }
}
