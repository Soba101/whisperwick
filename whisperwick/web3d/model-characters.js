import * as THREE from 'three';
import {loadModel,instance,replaceWith} from './models.js';
import {box,cone,cylinder,mesh,clothing,hash} from './geometry.js';

const identities={npc_hal:'male-a',npc_victor:'male-b',npc_bob:'male-c',
  npc_alice:'female-a',npc_sarah:'female-b',player:'female-c'};
export function modelCharacter(host,p,isPlayer) {
  replaceWith(host,async () => {
    const identity=identities[p.id] || ['male-a','male-b','male-c','female-a','female-b','female-c'][hash(p.id)%6];
    const gltf=await loadModel(`characters/character-${identity}.glb`);
    const group=new THREE.Group(), model=instance(gltf,{person:p.id,item:false},true);
    group.add(model);
    const bounds=new THREE.Box3().setFromObject(model), height=bounds.max.y-bounds.min.y;
    model.scale.setScalar(1.85/height); model.position.y=-bounds.min.y*model.scale.y;
    // Small identity props keep the existing palette legible without recolouring skin.
    const color=clothing(p.id), clothes=new THREE.Group(), hat=new THREE.Group();
    group.add(clothes,hat);
    box(clothes,.55,.42,.4,color,0,.85,.04);
    if(p.id==='npc_alice') box(clothes,.43,.45,.1,0xf1dfb9,0,.63,.27);
    if(p.id==='npc_hal') {
      cylinder(hat,.4,.16,0x8d9ba6,0,1.83,0); box(hat,.13,.2,.55,color,0,1.97,0);
    }
    if(p.id==='npc_victor') {
      cylinder(hat,.4,.12,color,0,1.83,0); cone(hat,.28,.3,color,0,2,0);
    }
    if(isPlayer) {
      const cloak=cone(clothes,.4,.85,color,0,.85,-.17); cloak.rotation.x=-.15;
      const ring=mesh(group,new THREE.RingGeometry(.48,.72,32),0xffdda1,0,.07,0,
        {transparent:true,opacity:.5,emissive:0xffc574,emissiveIntensity:.6,side:THREE.DoubleSide});
      ring.rotation.x=-Math.PI/2; ring.castShadow=false;
    }
    // Accessories follow the imported rig when it breathes, sits or reaches.
    group.updateMatrixWorld(true);
    model.getObjectByName('torso')?.attach(clothes);
    model.getObjectByName('head')?.attach(hat);
    group.traverse(o => {
      if(!o.isMesh) return;
      o.userData.pick={person:p.id,item:false}; o.userData.color=o.material.color.clone();
    });
    const mixer=new THREE.AnimationMixer(model), actions=new Map();
    gltf.animations.forEach(clip => actions.set(clip.name,mixer.clipAction(clip)));
    group.userData.actor={mixer,actions,current:null}; return group;
  });
}
export function pose(host,name,dt) {
  const actor=host.userData.actor; if(!actor) return;
  const action=actor.actions.get(name) || actor.actions.get('idle');
  if(action && actor.current!==action) {
    actor.current?.fadeOut(.15); action.reset().fadeIn(.15).play(); actor.current=action;
  }
  actor.mixer.update(dt);
}
