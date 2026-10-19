import * as THREE from 'three';
import {modelProp} from './model-scenery.js';
import {box,ball,cone,cylinder,mesh,batch,seeded,material} from './geometry.js';

export function pathCurve(a,b) {
  // Both feet and ribbons use this same curve. It never chooses a route.
  const middle = a.clone().add(b).multiplyScalar(.5).multiplyScalar(.78);
  middle.y = .19;
  return new THREE.QuadraticBezierCurve3(a.clone().setY(.19),middle,b.clone().setY(.19));
}
export function ribbon(curve,width=1.5) {
  const vertices = [], indices = [];
  for (let i=0;i<=32;i++) {
    const p = curve.getPoint(i/32), t = curve.getTangent(i/32);
    const side = new THREE.Vector3(-t.z,0,t.x).normalize().multiplyScalar(width/2);
    vertices.push(p.x+side.x,p.y,p.z+side.z,p.x-side.x,p.y,p.z-side.z);
    if (i<32) { const k=i*2; indices.push(k,k+2,k+1,k+1,k+2,k+3); }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
  geo.setIndex(indices); geo.computeVertexNormals();
  const m = new THREE.Mesh(geo,material(0xc6ae83,{side:THREE.DoubleSide}));
  m.receiveShadow = true; return m;
}
export function ground(scene,radius) {
  const g = new THREE.Group();
  cylinder(g,radius,2.4,0x725744,0,-1.35,0,80);
  cylinder(g,radius+.12,.45,0x8d7750,0,-.35,0,80);
  scene.add(batch(g));
  // Concentric rings allow a soft surface without raising building foundations.
  const vertices=[], indices=[];
  for(let ring=0;ring<=18;ring++) for(let i=0;i<=80;i++) {
    const a=i/80*Math.PI*2, r=radius*ring/18;
    vertices.push(Math.cos(a)*r,Math.sin(a)*r,0);
    if(ring<18 && i<80) {
      const k=ring*81+i; indices.push(k,k+1,k+81,k+1,k+82,k+81);
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3)); geo.setIndex(indices);
  const pos = geo.attributes.position, colors = [], c = new THREE.Color();
  for (let i=0;i<pos.count;i++) {
    const x=pos.getX(i), z=pos.getY(i);
    const h=.06*Math.sin(x*.42)*Math.cos(z*.38);
    pos.setXYZ(i,x,h,z);
    c.set(0x99ad70).multiplyScalar(.96+.07*Math.sin(x*.7+z*.4)); colors.push(c.r,c.g,c.b);
  }
  geo.setAttribute('color',new THREE.Float32BufferAttribute(colors,3)); geo.computeVertexNormals();
  const grass = new THREE.Mesh(geo,material(0xffffff,{vertexColors:true,side:THREE.DoubleSide}));
  grass.receiveShadow = true; scene.add(grass);
}
export function lamp(g,x,z,lights) {
  cylinder(g,.07,2.8,0x65523e,x,1.4,z,6);
  box(g,.42,.5,.42,0xffcf7d,x,2.8,z); cone(g,.38,.25,0x65523e,x,3.18,z,4);
  lights.push(new THREE.Vector3(x,2.8,z));
}
function tree(g,x,z,rand) {
  cylinder(g,.2,1.8,0x796044,x,.9,z,6);
  if (rand()>.5) {
    cone(g,1.4,2.6,0x668d68,x,2.5,z); cone(g,1,2,0x80a373,x,3.6,z);
  } else {
    ball(g,1.3,0x81a16b,x,2.8,z,1); ball(g,.9,0x9bb478,x+.7,2.7,z+.25);
  }
}
export function dress(scene,places,spots,curves,radius) {
  const g = new THREE.Group(), lights = [];
  const paths=curves.flatMap(c => c.getPoints(64));
  const clear=(x,z,margin=2.5) => Math.hypot(x,z)<radius-2 &&
    !paths.some(v => Math.hypot(v.x-x,v.z-z)<margin) &&
    ![...spots.values()].some(v => {
      const a=Math.atan2(-v.x,-v.z), dx=x-v.x, dz=z-v.z;
      const across=dx*Math.cos(a)-dz*Math.sin(a), front=dx*Math.sin(a)+dz*Math.cos(a);
      return Math.abs(across)<5.5 && front> -4.5 && front<11;
    });
  places.forEach(p => {
    const rand = seeded(p.id), spot = spots.get(p.id);
    for (let i=0;i<18;i++) {
      const a=rand()*Math.PI*2, d=6+rand()*5;
      const x=spot.x+Math.cos(a)*d, z=spot.z+Math.sin(a)*d;
      // Keep entrances and every path clear, including their click targets.
      if (!clear(x,z)) continue;
      const prop=new THREE.Group(), host=new THREE.Group();
      if (i<6) tree(prop,0,0,rand);
      else if (i<13) ball(prop,.65,0x67835d,0,.45,0,1);
      else ball(prop,.45,0x939080,0,.2,0);
      host.add(batch(prop)); host.position.set(x,0,z); scene.add(host);
      const name=i<6 ? (i%2 ? 'tree_pineRoundC' : 'tree_oak') : i<13 ? 'plant_bush' : 'rock_smallA';
      modelProp(host,'nature',name,i<6 ? [2.6,4.2,2.6] : i<13 ? [1.3,.9,1.3] : [.9,.55,.9]);
      for (let j=0;j<4;j++) {
        const fx=x+rand()*2-1, fz=z+rand()*2-1;
        if(!clear(fx,fz,2)) continue;
        cylinder(g,.025,.24,0x658052,fx,.12,fz,4);
        const flower=new THREE.Group(), fallback=new THREE.Group();
        ball(fallback,.1,[0xf0cb85,0xc58387,0xe6dcb6][j%3],0,.28,0);
        flower.add(batch(fallback)); flower.position.set(fx,0,fz); scene.add(flower);
        modelProp(flower,'nature','flower_redA',[.22,.38,.22]);
      }
    }
    // A short fence sits behind each place, away from the entrance.
    const fence=new THREE.Group(), rails=new THREE.Group();
    for (let j=0;j<4;j++) box(rails,.12,.9,.12,0xb29970,-2+j*1.3,.45,0);
    [ .35,.7 ].forEach(y => box(rails,4.1,.1,.1,0xb29970,-.05,y,0));
    fence.add(batch(rails)); const facing=Math.atan2(-spot.x,-spot.z);
    fence.position.copy(new THREE.Vector3(0,0,-4).applyAxisAngle(new THREE.Vector3(0,1,0),facing).add(spot));
    fence.rotation.y=facing; scene.add(fence);
    modelProp(fence,'town',p.id==='loc_temple' ? 'hedge' : 'fence',[4.1,.9,.3]);
  });
  // Fill the gaps with small seeded groves rather than an evenly dotted lawn.
  const rand=seeded('island_groves');
  for(let i=0;i<20;i++) {
    const a=rand()*Math.PI*2, d=5+rand()*(radius-8), cx=Math.cos(a)*d, cz=Math.sin(a)*d;
    for(let j=0;j<3;j++) {
      const x=cx+(rand()-.5)*4, z=cz+(rand()-.5)*4;
      if(!clear(x,z,3) || Math.hypot(x,z)<4) continue;
      const host=new THREE.Group(), fallback=new THREE.Group();
      tree(fallback,0,0,rand); host.add(batch(fallback)); host.position.set(x,0,z); scene.add(host);
      modelProp(host,'nature',j%2 ? 'tree_pineRoundC' : 'tree_oak',[2.5,3.4+rand(),2.5]);
    }
  }
  curves.forEach(c => [.28,.65].forEach(u => {
    const p=c.getPoint(u), t=c.getTangent(u), side=new THREE.Vector3(-t.z,0,t.x).normalize();
    const position=p.clone().addScaledVector(side,2.3);
    if(!clear(position.x,position.z,1.5)) return;
    lamp(g,position.x,position.z,lights);
    const fence=new THREE.Group(); fence.position.copy(p).addScaledVector(side,-2.7).setY(0);
    if(!clear(fence.position.x,fence.position.z,1.5)) return;
    fence.rotation.y=Math.atan2(-t.z,t.x); scene.add(fence);
    const rails=new THREE.Group();
    [-1.5,0,1.5].forEach(x => box(rails,.12,.9,.12,0xb29970,x,.45,0));
    [.35,.7].forEach(y => box(rails,3,.1,.1,0xb29970,0,y,0)); fence.add(batch(rails));
    modelProp(fence,'town','fence',[3,.9,.3]);
  }));
  // The well anchors the empty centre of the diorama.
  const well = mesh(g,new THREE.CylinderGeometry(.9,.95,.9,12,1,true),0xb5b5a0,0,.5,0,
    {side:THREE.DoubleSide}); well.receiveShadow=true;
  cylinder(g,.8,.08,0x4e737a,0,.15,0);
  [-1.1,1.1].forEach(x => box(g,.14,2.6,.14,0x69503d,x,1.3,0));
  cone(g,1.6,1,0xa65c45,0,3,0,4).rotation.y=Math.PI/4;
  scene.add(batch(g)); return lights;
}
