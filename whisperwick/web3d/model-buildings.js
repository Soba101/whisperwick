import * as THREE from 'three';
import {piece,pieces,dispose,replaceWith} from './models.js';
import {box,mesh,cylinder,hash} from './geometry.js';

// Each recipe uses stable place IDs. It says nothing about available actions.
export function modelBuilding(host,place) {
  replaceWith(host,async () => {
    const g=new THREE.Group(), jobs=[], pick={place:place.id};
    const add=(name,size,pos,angle=0) => jobs.push(piece('town',name,size,pos,angle,pick));
    const windowGlow=(x,y,z,round=false) => {
      const geo=round ? new THREE.CircleGeometry(.34,16) : new THREE.PlaneGeometry(.58,.75);
      const m=mesh(g,geo,0xffc474,x,y,z,{emissive:0xffc474,emissiveIntensity:0});
      m.userData.window=true; m.userData.pick=pick;
    };
    const shell=(wood,w,d,floors=1,arched=false) => {
      const tile=wood ? 'wall-wood' : 'wall', h=2.45, bay=w/3;
      for(let floor=0;floor<floors;floor++) {
        for(let i=0;i<3;i++) {
          const x=(i-1)*bay, y=floor*h;
          const front=i===1 && floor===0 ? (wood ? 'wall-wood-door' : 'wall-door') :
            arched ? 'wall-window-round' : wood ? 'wall-wood-window-glass' : 'wall-window-glass';
          add(front,[.22,h,bay],[x,y,d/2],-Math.PI/2);
          add(tile,[.22,h,bay],[x,y,-d/2],Math.PI/2);
          if(i!==1 || floor>0) windowGlow(x,y+1.55,d/2+.13,arched);
        }
        [-1,1].forEach(side => add(arched ? 'wall-arch' : tile,[.22,h,d],
          [side*w/2,floor*h,0],side<0 ? Math.PI : 0));
      }
      add(arched ? 'roof-high-point' : 'roof-gable',[w+.6,arched ? 3.4 : 1.8,d+.6],[0,h*floors,0]);
    };
    const recipes={
      loc_inn:() => {
        shell(true,5.4,4.2,2); add('chimney',[.7,2.3,.8],[1.8,5,0]);
        add('banner-red',[.16,1.3,.85],[3,2.6,2.2],-Math.PI/2);
      },
      loc_market:() => {
        [[-2.8,-1.8],[2.8,-1.8],[-2.8,2],[2.8,2]].forEach(([x,z],i) => {
          add(['stall-red','stall-green','stall','stall-red'][i],[2.5,2.8,2.2],[x,0,z]);
          add('stall-stool',[.5,.65,.5],[x+.9,0,z+1.4]);
        });
        add('fountain-round',[2.5,.5,2.5],[0,0,0]);
        add('fountain-center',[.6,1.5,.6],[0,0,0]); add('cart',[1.5,1.3,2],[-4.5,0,0]);
      },
      loc_temple:() => {
        shell(false,4.5,4.5,2,true);
        for(let i=0;i<3;i++) box(g,2.4-i*.25,.2,1.5-i*.25,0xb5b5a0,0,.1+i*.2,2.8-i*.25);
      },
      loc_town_hall:() => {
        shell(false,7,4.2,1); add('roof-high-point',[2.3,4.5,2.5],[0,4,0]);
        [-2.7,2.7].forEach(x => add('banner-green',[.12,1.3,.7],[x,2.5,2.4],-Math.PI/2));
        cylinder(g,.51,.15,0xf1dcaa,0,5.8,1.32,20).rotation.x=Math.PI/2;
        box(g,.06,.4,.06,0x69503d,0,6,1.45); box(g,.35,.06,.06,0x69503d,.15,5.8,1.45);
        box(g,.08,1.4,.08,0x69503d,1.1,7.4,0); box(g,.9,.55,.05,0xa65248,1.58,7.75,0);
        // Keep the public custody spot and bars aligned with the fallback hall.
        box(g,1.8,1.8,.12,0x494e49,2.3,1.25,2.18);
        for(let i=0;i<6;i++) box(g,.07,1.8,.12,0x767d79,1.48+i*.33,1.25,2.65);
      },
    };
    (recipes[place.id] || (() => shell(true,4.8,4)))();
    try { (await pieces(jobs)).forEach(p => g.add(p)); }
    catch(error) { dispose(g); throw error; }
    if(!recipes[place.id]) {
      // A new scenario still gets a stable roof colour without a custom recipe.
      g.children.at(-1).traverse(o => {
        if(o.isMesh) o.material.color.set([0xc88d70,0x8899ac,0x9da978][hash(place.id)%3]);
      });
    }
    return g;
  });
}
export function lightWindows(group,daylight) {
  group.traverse(o => { if(o.userData.window) o.material.emissiveIntensity=(1-daylight)*1.8; });
}
