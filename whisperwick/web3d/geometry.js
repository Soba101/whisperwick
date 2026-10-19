import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

// These hashes are paint and scenery seeds, never world state.
export function hash(id) {
  let n = 2166136261;
  for (const c of id) n = Math.imul(n ^ c.charCodeAt(0), 16777619);
  return n >>> 0;
}
export function seeded(id) {
  let n = hash(id);
  return () => { n = (Math.imul(n, 1664525) + 1013904223) >>> 0; return n / 4294967296; };
}
export {clothing} from './palette.js';
export function material(color, extra={}) {
  return new THREE.MeshStandardMaterial({color,roughness:.9,...extra});
}
export function mesh(group, geometry, color, x=0,y=0,z=0, extra={}) {
  const m = new THREE.Mesh(geometry,material(color,extra));
  m.position.set(x,y,z); m.castShadow = true; m.receiveShadow = true; group.add(m); return m;
}
export function box(g,w,h,d,c,x=0,y=0,z=0) {
  // A tiny chamfer catches the sun along stone and timber edges.
  const s = new THREE.Shape(), b = Math.min(.065,w/8,h/8,d/8);
  s.moveTo(-w/2+b,-h/2+b); s.lineTo(w/2-b,-h/2+b);
  s.lineTo(w/2-b,h/2-b); s.lineTo(-w/2+b,h/2-b); s.closePath();
  const geo = new THREE.ExtrudeGeometry(s,{depth:d-2*b,bevelEnabled:true,
    bevelSegments:1,steps:1,bevelSize:b,bevelThickness:b});
  geo.translate(0,0,-d/2+b); return mesh(g,geo,c,x,y,z);
}
export function ball(g,r,c,x,y,z,detail=0) {
  return mesh(g,new THREE.IcosahedronGeometry(r,detail),c,x,y,z);
}
export function cone(g,r,h,c,x,y,z,n=8) {
  return mesh(g,new THREE.ConeGeometry(r,h,n),c,x,y,z);
}
export function cylinder(g,r,h,c,x,y,z,n=10) {
  return mesh(g,new THREE.CylinderGeometry(r,r,h,n),c,x,y,z);
}
// Merge by material inside each selectable object. Picking still uses stable IDs.
export function batch(group,pick) {
  group.updateMatrixWorld(true);
  const buckets = new Map(), old = [];
  group.traverse(o => {
    if (!o.isMesh) return;
    const mat=o.material;
    const key=[mat.color.getHex(),mat.emissive.getHex(),mat.emissiveIntensity,
      mat.side,mat.transparent,mat.opacity,mat.depthWrite,o.castShadow,o.receiveShadow].join(':');
    if (!buckets.has(key)) buckets.set(key,{material:mat,geometries:[],cast:o.castShadow,receive:o.receiveShadow});
    const geo = o.geometry.clone().applyMatrix4(o.matrixWorld);
    // Indexed primitives must be expanded before sharing a vertex stream.
    const flat = geo.index ? geo.toNonIndexed() : geo;
    flat.deleteAttribute('uv'); buckets.get(key).geometries.push(flat); old.push(o);
    if (flat !== geo) geo.dispose();
  });
  const result = new THREE.Group();
  for (const {material,geometries,cast,receive} of buckets.values()) {
    const m = new THREE.Mesh(mergeGeometries(geometries),material);
    m.castShadow = cast; m.receiveShadow = receive; m.userData.pick = pick; result.add(m);
    geometries.forEach(g => g.dispose());
  }
  const retained=new Set([...buckets.values()].map(b => b.material));
  old.forEach(o => { o.geometry.dispose(); if(!retained.has(o.material)) o.material.dispose(); });
  return result;
}
