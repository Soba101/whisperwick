import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {Figures} from './figures.js';
import {Labels} from './labels.js';
import {building} from './buildings.js';
import {ground,dress,pathCurve,ribbon} from './nature.js';
import {modelRoad} from './model-scenery.js';
import {lightWindows} from './model-buildings.js';
import {Sky} from './sky.js';

// All coordinates are cosmetic. Place membership always comes from Python.
export class Village {
  constructor(pick) {
    this.pick=pick; this.scene=new THREE.Scene(); this.labels=new Labels(pick);
    this.camera=new THREE.PerspectiveCamera(42,1,.1,400);
    this.camera.position.set(39,43,53);
    this.renderer=new THREE.WebGLRenderer({antialias:true});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));
    this.renderer.outputColorSpace=THREE.SRGBColorSpace;
    this.renderer.toneMapping=THREE.ACESFilmicToneMapping; this.renderer.toneMappingExposure=1.15;
    this.renderer.shadowMap.enabled=true; this.renderer.shadowMap.type=THREE.PCFSoftShadowMap;
    document.getElementById('canvas').append(this.renderer.domElement);
    this.controls=new OrbitControls(this.camera,this.renderer.domElement);
    this.controls.enableDamping=true; this.controls.dampingFactor=.065;
    this.controls.maxPolarAngle=Math.PI/2.25; this.controls.minPolarAngle=.2;
    this.controls.minDistance=12; this.controls.maxDistance=125;
    this.controls.addEventListener('start',() => { this.goal=null; this.follow=false; });
    this.links=new Map(); this.spots=new Map(); this.curves=new Map(); this.follow=false;
    this.smoke=[]; this.figures=new Figures(this);
    new ResizeObserver(() => this.resize()).observe(document.getElementById('village'));
    // Ignore drags: orbiting must not also send a move.
    const canvas=this.renderer.domElement;
    canvas.addEventListener('pointerdown',e => this.down=[e.clientX,e.clientY]);
    canvas.addEventListener('pointerup',e => {
      if(!this.down || Math.hypot(e.clientX-this.down[0],e.clientY-this.down[1])>6) return;
      const r=canvas.getBoundingClientRect(),ray=new THREE.Raycaster();
      ray.setFromCamera(new THREE.Vector2((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1),this.camera);
      const hit=ray.intersectObjects(this.scene.children,true).find(h => h.object.userData.pick);
      if(hit) this.pick(hit.object.userData.pick);
    });
    this.resize(); this.animate();
  }
  resize() {
    const box=document.getElementById('village');
    this.renderer.setSize(box.clientWidth,box.clientHeight);
    this.camera.aspect=box.clientWidth/box.clientHeight; this.camera.updateProjectionMatrix();
  }
  entrance(id) { return this.spots.get(id).clone().add(new THREE.Vector3(0,.2,5.5)); }
  build(places) {
    const radius=Math.max(17,places.length*2.5), island=radius+12;
    this.sky=new Sky(this.scene,this.renderer,island); ground(this.scene,island);
    // Sorting stable IDs also makes reordered YAML produce the same village.
    [...places].sort((a,b) => a.id.localeCompare(b.id)).forEach((p,i) => {
      const a=i*Math.PI*2/places.length;
      const spot=new THREE.Vector3(Math.cos(a)*radius,0,Math.sin(a)*radius);
      this.spots.set(p.id,spot); this.links.set(p.id,p.links);
      const b=building(p,spot); this.scene.add(b.group);
      this.labels.add(p.name,spot.clone().add(new THREE.Vector3(0,b.height,0)),{place:p.id},'place');
      b.smoke.forEach(position => this.addSmoke(position));
      if(p.id!=='loc_market') this.sky.addLamps([spot.clone().add(new THREE.Vector3(-1.4,2,3))]);
    });
    const drawn=new Set();
    places.forEach(p => p.links.forEach(id => {
      const key=[p.id,id].sort().join('|');
      if(drawn.has(key) || !this.spots.has(id)) return;
      drawn.add(key);
      const [a,b]=[p.id,id].sort(), curve=pathCurve(this.entrance(a),this.entrance(b));
      this.curves.set(key,curve);
      const road=new THREE.Group(); road.add(ribbon(curve)); this.scene.add(road); modelRoad(road,curve);
    }));
    this.sky.addLamps(dress(this.scene,places,this.spots,[...this.curves.values()],island));
    // Fit the entire base on both portrait and landscape viewports.
    const distance=island*1.1/Math.sin(THREE.MathUtils.degToRad(21)*Math.min(1,this.camera.aspect));
    this.camera.position.set(.5,.62,.72).normalize().multiplyScalar(distance);
    this.controls.maxDistance=Math.max(125,distance*1.4);
  }
  addSmoke(position) {
    // Shared geometry and material keep the chimney's soft puffs inexpensive.
    const geo=new THREE.IcosahedronGeometry(.28,1);
    const mat=new THREE.MeshBasicMaterial({color:0xe2d8c9,transparent:true,opacity:.18,depthWrite:false});
    for(let i=0;i<5;i++) {
      const puff=new THREE.Mesh(geo,mat.clone()); this.scene.add(puff); this.smoke.push({puff,position,phase:i/5});
    }
    mat.dispose();
  }
  focus(id) { if(this.spots.has(id)) this.goal=this.spots.get(id).clone(); }
  update(s) {
    if(!this.spots.size) this.build(s.places);
    this.sky.update(s); this.figures.update(s); this.daylight=s.daylight;
  }
  animate() {
    requestAnimationFrame(() => this.animate());
    const now=performance.now(), dt=Math.min(.05,(now-(this.last || now))/1000); this.last=now;
    this.figures.animate(now);
    const target=this.follow && this.figures.player ? this.figures.player.group.position : this.goal;
    if(target) {
      const delta=target.clone().sub(this.controls.target).multiplyScalar(1-Math.exp(-dt*4));
      this.controls.target.add(delta); this.camera.position.add(delta);
    }
    this.smoke.forEach(({puff,position,phase}) => {
      const t=(now/7000+phase)%1; puff.position.copy(position).add(new THREE.Vector3(t*.8,t*2.8,Math.sin(t*4)*.15));
      puff.scale.setScalar(.5+t*2); puff.material.opacity=.22*(1-t);
    });
    this.controls.update(); this.camera.updateMatrixWorld(); this.sky?.animate(this.camera);
    this.labels.draw(this.camera,this.renderer.domElement.clientWidth,this.renderer.domElement.clientHeight,now);
    lightWindows(this.scene,this.daylight ?? 1);
    this.renderer.render(this.scene,this.camera);
  }
}
