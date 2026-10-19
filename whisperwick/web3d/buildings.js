import * as THREE from 'three';
import {modelBuilding} from './model-buildings.js';
import {box,ball,cone,cylinder,mesh,batch,hash} from './geometry.js';

const plaster = 0xe6cba0, wood = 0x69503d, stone = 0xb5b5a0, gold = 0xffc474;
function window(g,x,y,z,w=.6,h=.75) {
  box(g,w+.18,h+.18,.14,wood,x,y,z);
  mesh(g,new THREE.PlaneGeometry(w,h),gold,x,y,z+.08,
    {emissive:gold,emissiveIntensity:.65});
  box(g,.07,h,.08,wood,x,y,z+.1);
}
function roof(g,w,d,y,color) {
  // A triangular prism gives every house a real pitched silhouette.
  const shape = new THREE.Shape();
  shape.moveTo(-w/2,0); shape.lineTo(0,1.8); shape.lineTo(w/2,0); shape.closePath();
  const geo = new THREE.ExtrudeGeometry(shape,{depth:d,bevelEnabled:true,
    bevelSegments:1,steps:1,bevelSize:.06,bevelThickness:.06});
  geo.translate(0,0,-d/2); mesh(g,geo,color,0,y,0);
}
function door(g,y=.9,z=2.08) { box(g,.8,1.8,.15,wood,0,y,z); ball(g,.06,gold,.25,y,z+.13); }
function cottage(g,id) {
  box(g,4.8,2.8,4,plaster,0,1.4,0); door(g);
  window(g,-1.45,1.6,2.08); window(g,1.45,1.6,2.08);
  roof(g,5.3,4.7,2.9,[0xa65c45,0x657789,0x737f51][hash(id)%3]);
}
function inn(g,smoke) {
  box(g,5.4,4.9,4.2,plaster,0,2.45,0); roof(g,6,4.9,5,0xa65c45); door(g,1,2.18);
  [-2.5,0,2.5].forEach(x => box(g,.17,4.9,.18,wood,x,2.45,2.2));
  [2.65,4.8].forEach(y => box(g,5.4,.18,.18,wood,0,y,2.2));
  [-1.35,1.35].forEach(x => { window(g,x,1.6,2.2); window(g,x,3.7,2.2); });
  box(g,.7,2.3,.8,stone,1.8,6,0);
  box(g,.15,1.5,.15,wood,3.3,3,1.5); box(g,1.4,.12,.15,wood,3,3.7,1.5);
  box(g,1.1,.85,.18,0xc59c63,3.6,3.05,1.5);
  cylinder(g,.19,.42,gold,3.6,3.05,1.64).rotation.x = Math.PI/2;
  smoke.push(new THREE.Vector3(1.8,7.3,0));
}
function market(g) {
  cylinder(g,4.5,.15,0xc0a47b,0,.06,0,24);
  [[-2,-1],[2,-1],[-2,2],[2,2]].forEach(([x,z],i) => {
    box(g,2.5,.8,1.25,wood,x,.6,z);
    [-1.15,1.15].forEach(dx => box(g,.1,2.4,.1,wood,x+dx,1.4,z));
    for (let j=0;j<6;j++) {
      const awning = box(g,.44,.12,2.2,j%2 ? 0xf1dbad : [0xb65c4f,0x638878][i%2],
        x-1.1+j*.44,2.6,z);
      awning.rotation.x = -.12;
    }
    box(g,.7,.65,.7,0xb48b54,x+1.25,.34,z+1.1);
    cylinder(g,.38,.85,0x8c6749,x-1.2,.44,z+1.2);
    for (let j=0;j<3;j++) ball(g,.16,0xc69449,x-.6+j*.5,1.12,z);
  });
}
function temple(g) {
  box(g,4.5,3.8,4.5,stone,0,2,0); roof(g,5,5,3.95,0x6d7b86);
  box(g,1.6,6.8,1.8,stone,-2,3.4,0);
  cone(g,1.35,3,0x657789,-2,8.2,0,4).rotation.y = Math.PI/4;
  for (let i=0;i<3;i++) box(g,2.4-i*.25,.2,1.5-i*.25,stone,0,.1+i*.2,2.5-i*.25);
  door(g,1.4,2.33);
  cylinder(g,.55,.12,wood,0,3.1,2.34,16).rotation.x = Math.PI/2;
  cylinder(g,.4,.14,gold,0,3.1,2.43,16).rotation.x = Math.PI/2;
  box(g,.15,.9,.12,wood,0,3.1,2.55); box(g,.9,.15,.12,wood,0,3.1,2.55);
}
function hall(g) {
  box(g,7,3.5,4.2,stone,0,1.75,0); roof(g,7.6,4.8,3.6,0x73815a);
  box(g,1.8,6.8,2,plaster,0,3.4,-.2); roof(g,2.3,2.5,6.9,0x73815a);
  cylinder(g,.63,.15,wood,0,5.8,.88,20).rotation.x = Math.PI/2;
  cylinder(g,.51,.18,0xf1dcaa,0,5.8,.97,20).rotation.x = Math.PI/2;
  box(g,.06,.4,.06,wood,0,6,1.1); box(g,.35,.06,.06,wood,.15,5.8,1.1);
  box(g,.08,2,.08,wood,1.1,7,0); box(g,.9,.55,.05,0xa65248,1.58,7.55,0);
  door(g,1,2.18); window(g,-2.4,2,2.18);
  // The visible cell occupies the right bay; held figures stand behind these bars.
  box(g,1.8,1.8,.12,0x494e49,2.3,1.25,2.18);
  for (let i=0;i<6;i++) box(g,.07,1.8,.12,0x767d79,1.48+i*.33,1.25,2.65);
  box(g,1.9,.09,.14,0x767d79,2.3,1.25,2.65);
}
export function building(place,spot) {
  const g = new THREE.Group(), smoke = [];
  const builders = {loc_inn:() => inn(g,smoke),loc_market:() => market(g),
    loc_temple:() => temple(g),loc_town_hall:() => hall(g)};
  (builders[place.id] || (() => cottage(g,place.id)))();
  const group=new THREE.Group(); group.add(batch(g,{place:place.id}));
  group.position.copy(spot); modelBuilding(group,place);
  return {group,height:({loc_temple:10,loc_town_hall:9,loc_inn:8,loc_market:3.8})[place.id] || 6,
    smoke:smoke.map(p => p.add(spot))};
}
