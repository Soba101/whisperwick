import * as THREE from 'three';
import {seeded} from './geometry.js';

export class Sky {
  constructor(scene,renderer,radius) {
    this.scene=scene; this.renderer=renderer; this.lamps=[];
    this.hemi = new THREE.HemisphereLight(0xffe4b5,0x64704e,2); scene.add(this.hemi);
    this.sun = new THREE.DirectionalLight(0xffd6a0,3); this.sun.castShadow=true;
    this.sun.shadow.mapSize.set(2048,2048);
    Object.assign(this.sun.shadow.camera,{left:-radius,right:radius,top:radius,bottom:-radius,near:1,far:150});
    this.sun.shadow.normalBias=.04; this.sun.shadow.bias=-.0003; this.sun.shadow.radius=3;
    scene.add(this.sun); scene.add(this.sun.target);
    this.uniforms={top:{value:new THREE.Color()},bottom:{value:new THREE.Color()}};
    const mat = new THREE.ShaderMaterial({side:THREE.BackSide,depthWrite:false,
      uniforms:this.uniforms,vertexShader:`varying vec3 direction;
        void main(){direction=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
      fragmentShader:`varying vec3 direction; uniform vec3 top; uniform vec3 bottom;
        void main(){float h=smoothstep(-.1,.85,normalize(direction).y);
        gl_FragColor=vec4(mix(bottom,top,h),1.);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
        }`});
    this.dome=new THREE.Mesh(new THREE.SphereGeometry(180,24,16),mat);
    this.dome.frustumCulled=false; scene.add(this.dome);
    const rand=seeded('sky_stars'), points=[];
    for(let i=0;i<220;i++) {
      const a=rand()*Math.PI*2, h=.12+rand()*.86, r=Math.sqrt(1-h*h);
      points.push(160*r*Math.cos(a),160*h,160*r*Math.sin(a));
    }
    const geo=new THREE.BufferGeometry(); geo.setAttribute('position',new THREE.Float32BufferAttribute(points,3));
    this.stars=new THREE.Points(geo,new THREE.PointsMaterial({color:0xffe9c1,size:.38,
      transparent:true,depthWrite:false,fog:false})); scene.add(this.stars);
    scene.fog=new THREE.Fog(0xc9d5cc,65,145);
  }
  addLamps(positions) {
    // Only the sun casts shadows; short lamp ranges keep evening rendering cheap.
    positions.forEach(p => {
      const light=new THREE.PointLight(0xffbc68,0,7,2); light.position.copy(p);
      this.scene.add(light); this.lamps.push(light);
    });
  }
  update(s) {
    const match=s.clock.match(/(\d{1,2}):(\d{2})/);
    const hour=match ? Number(match[1])+Number(match[2])/60 : 12;
    const light=THREE.MathUtils.clamp(s.daylight,0,1), night=1-THREE.MathUtils.smoothstep(light,0,.5);
    const top=light<.1 ? 0x152440 : light<.65 ? (hour<12 ? 0xa18aaa : 0x9b758e) : 0x8cbad0;
    const bottom=light<.1 ? 0x394663 : light<.65 ? (hour<12 ? 0xeab5aa : 0xe6aa79) : 0xdce0be;
    this.uniforms.top.value.set(top); this.uniforms.bottom.value.set(bottom);
    this.scene.fog.color.set(bottom); this.renderer.setClearColor(bottom);
    const angle=(hour-6)/12*Math.PI;
    this.sun.position.set(Math.cos(angle)*42,Math.max(5,Math.sin(angle)*48),20);
    this.sun.color.set(light<.65 ? 0xffbc8b : 0xffe0af); this.sun.intensity=.12+light*3.1;
    this.hemi.intensity=.65+light*1.25; this.stars.material.opacity=night*.9;
    this.lamps.forEach(l => l.intensity=night*7);
  }
  animate(camera) { this.dome.position.copy(camera.position); this.stars.position.copy(camera.position); }
}
