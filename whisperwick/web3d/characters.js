import * as THREE from 'three';
import {modelCharacter} from './model-characters.js';
import {box,ball,cone,cylinder,mesh,clothing,hash,batch} from './geometry.js';

export function character(p,isPlayer) {
  const g=new THREE.Group(), color=clothing(p.id);
  cone(g,.36,.8,color,0,.75,0,8);
  [-.16,.16].forEach(x => { box(g,.2,.36,.25,0x554c42,x,.22,0); });
  [-.4,.4].forEach(x => {
    const arm=box(g,.18,.55,.2,color,x,.82,0); arm.rotation.z=x>0 ? -.16 : .16;
    ball(g,.11,0xe0b68d,x,.52,0);
  });
  ball(g,.33,0xe0b68d,0,1.4,0,1);
  const hair=mesh(g,new THREE.SphereGeometry(.345,8,4,0,Math.PI*2,0,Math.PI*.48),
    p.id==='npc_hal' ? 0x8d9ba6 : [0x614736,0x423d38,0xb18c57][hash(p.id)%3],0,1.48,0);
  hair.scale.y=.75;
  [-.12,.12].forEach(x => ball(g,.035,0x3a3633,x,1.43,.3));
  if (p.id==='npc_alice') box(g,.43,.5,.1,0xf1dfb9,0,.67,.25);
  if (p.id==='npc_victor') { cylinder(g,.37,.12,0x644978,0,1.75,0); cone(g,.25,.32,0x86619c,0,1.95,0); }
  if (p.id==='npc_hal') box(g,.12,.25,.58,0x8d9ba6,0,1.74,0);
  if (isPlayer) {
    const cloak=cone(g,.44,.95,0x487875,0,.83,-.1); cloak.rotation.x=-.15;
    // A soft ring is a view marker, never a claim about ability or status.
    const ring=mesh(g,new THREE.RingGeometry(.48,.72,32),0xffdda1,0,.07,0,
      {transparent:true,opacity:.5,emissive:0xffc574,emissiveIntensity:.6,side:THREE.DoubleSide});
    ring.rotation.x=-Math.PI/2; ring.castShadow=false;
  }
  const result=batch(g,{person:p.id,item:false});
  // Each figure owns its merged materials so held tint never recolours a neighbour.
  result.children.forEach(m => {
    const old=m.material; m.material=old.clone(); old.dispose();
    m.userData.color=m.material.color.clone();
  });
  const host=new THREE.Group(); host.scale.setScalar(1.6); host.add(result); modelCharacter(host,p,isPlayer);
  return host;
}
export function tint(group,grey) {
  group.traverse(m => {
    if(!m.isMesh || !m.userData.color) return;
    m.material.color.copy(grey ? new THREE.Color(0x898b86) : m.userData.color);
    // Desaturate the texture as well; multiplying grey alone leaves coloured clothing.
    m.material.userData.grey=grey;
    if(!m.material.userData.tintShader) {
      m.material.userData.tintShader=true;
      m.material.onBeforeCompile=shader => {
        shader.uniforms.heldGrey={value:m.material.userData.grey ? 1 : 0}; m.material.userData.shader=shader;
        shader.fragmentShader='uniform float heldGrey;\n'+shader.fragmentShader.replace(
          '#include <color_fragment>',`#include <color_fragment>
          diffuseColor.rgb=mix(diffuseColor.rgb,vec3(dot(diffuseColor.rgb,vec3(.299,.587,.114))),heldGrey);`);
      };
    }
    const shader=m.material.userData.shader;
    if(shader) shader.uniforms.heldGrey.value=grey ? 1 : 0;
  });
}
