import * as THREE from 'three';
import {modelProp} from './model-scenery.js';
import {box,ball,cone,cylinder,mesh,batch} from './geometry.js';

// Names choose a visible prop only; all ownership and actions still come from Python.
export function item(p) {
  const g=new THREE.Group(), name=p.name.toLowerCase();
  if (/mug|cup/.test(name)) {
    mesh(g,new THREE.CylinderGeometry(.19,.15,.32,10,1,true),0xd7c49e,0,.2,0,{side:THREE.DoubleSide});
    const handle=mesh(g,new THREE.TorusGeometry(.13,.04,5,10),0xd7c49e,.2,.22,0); handle.rotation.y=.4;
  } else if (/bread|loaf/.test(name)) {
    const loaf=ball(g,.3,0xc99451,0,.2,0,1); loaf.scale.set(1.5,.7,.8);
    [-.15,0,.15].forEach(x => box(g,.035,.025,.33,0xe6c38a,x,.4,0));
  } else if (/coin/.test(name)) {
    cylinder(g,.22,.07,0xc79746,0,.09,0,16);
    cylinder(g,.13,.075,0xe5bd68,0,.095,0,16);
  } else if (/lantern|candle/.test(name)) {
    const lantern=name.includes('lantern');
    cylinder(g,lantern ? .23 : .12,lantern ? .38 : .32,0xf4cf82,0,.23,0,8);
    cone(g,.08,.18,0xffd57d,0,.5,0);
    if (lantern) {
      [0,.45].forEach(y => box(g,.5,.07,.4,0x65523e,0,y,0));
      [-.2,.2].forEach(x => box(g,.04,.45,.04,0x65523e,x,.23,.18));
    }
  } else if (/knife/.test(name)) {
    box(g,.12,.1,.35,0x69503d,0,.12,.18); cone(g,.1,.55,0xb9c6c7,0,.12,-.23,3).rotation.x=-Math.PI/2;
  } else {
    box(g,.48,.45,.48,0xb48b54,0,.24,0);
    [-.16,.16].forEach(x => box(g,.05,.48,.5,0x806344,x,.24,0));
  }
  const group=new THREE.Group(); group.add(batch(g,{person:p.id,item:true}));
  if (/cart|lantern/.test(name)) {
    const host=new THREE.Group(); host.add(...[...group.children]); group.add(host);
    modelProp(host,'town',name.includes('cart') ? 'cart' : 'lantern',
      name.includes('cart') ? [1.2,1,1.6] : [.35,.75,.35],{person:p.id,item:true});
  }
  if (/lantern|candle/.test(name)) {
    const glow=new THREE.PointLight(0xffbd62,.7,2); glow.position.y=.6; group.add(glow);
    group.userData.glow=glow;
  }
  return group;
}
