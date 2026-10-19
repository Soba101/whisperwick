import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {clone} from 'three/addons/utils/SkeletonUtils.js';

// Every Kenney model points at the same colormap.png: the file cache fetches it once.
THREE.Cache.enabled=true;
const loader=new GLTFLoader(), cache=new Map();
// A failed request is cached too. Polling must never hammer a missing asset.
export function loadModel(path) {
  if(!cache.has(path)) cache.set(path,loader.loadAsync(new URL('./assets/'+path,import.meta.url).href).then(gltf => {
    // Nature Kit colours are embedded, but its export marks bark and leaves metallic.
    // Dielectric materials keep them visible without an environment reflection map.
    if(path.startsWith('nature/')) gltf.scene.traverse(o => {
      if(!o.isMesh) return;
      o.material.metalness=0; o.material.roughness=1;
      if(/leaf|grass/i.test(o.material.name)) o.material.color.lerp(new THREE.Color(0x9cba78),.25);
    });
    return gltf;
  }));
  return cache.get(path);
}
export function instance(gltf,pick,animated=false) {
  const group=animated ? clone(gltf.scene) : gltf.scene.clone(true);
  group.traverse(o => {
    if(!o.isMesh) return;
    o.castShadow=true; o.receiveShadow=true; o.userData.pick=pick;
    o.userData.sharedModel=true;
    // Geometry and textures belong to the cache; tint belongs to this instance.
    o.material=o.material.clone(); o.userData.color=o.material.color.clone();
  });
  return group;
}
export function dispose(group) {
  group.userData.disposed=true;
  group.userData.actor?.mixer.stopAllAction();
  group.traverse(o => {
    if(!o.userData.sharedModel) o.geometry?.dispose();
    o.material?.dispose(); o.skeleton?.dispose();
  });
}
// Keep the old props until the complete replacement has loaded successfully.
export function replaceWith(host,build) {
  build().then(model => {
    if(host.userData.disposed) { dispose(model); return; }
    [...host.children].forEach(child => { host.remove(child); dispose(child); });
    host.add(model);
    if(model.userData.actor) host.userData.actor=model.userData.actor;
  }).catch(error => console.warn('Keeping procedural scenery:',error.message));
}
export async function piece(pack,name,size,position=[0,0,0],rotation=0,pick) {
  const model=instance(await loadModel(`${pack}/${name}.glb`),pick);
  // Pack origins vary. Fit in local axes before rotating a wall to its side.
  const bounds=new THREE.Box3().setFromObject(model), extent=bounds.getSize(new THREE.Vector3());
  const wrapper=new THREE.Group(); wrapper.add(model);
  model.position.set(-(bounds.min.x+extent.x/2),-bounds.min.y,-(bounds.min.z+extent.z/2));
  wrapper.scale.set(...size.map((s,i) => s/Math.max(.001,extent.getComponent(i))));
  const placed=new THREE.Group(); placed.add(wrapper);
  placed.rotation.y=rotation; placed.position.set(...position); return placed;
}

export async function pieces(jobs) {
  const results=await Promise.allSettled(jobs), failed=results.find(r => r.status==='rejected');
  if(failed) {
    results.filter(r => r.status==='fulfilled').forEach(r => dispose(r.value));
    throw failed.reason;
  }
  return results.map(r => r.value);
}
