import * as THREE from 'three';
import {seeded} from './geometry.js';

export class Sky {
  constructor(scene,renderer,radius) {
    this.scene=scene; this.renderer=renderer; this.lamps=[]; this.radius=radius;
    this.hemi = new THREE.HemisphereLight(0xdceeff,0xc5b595,2.5); scene.add(this.hemi);
    this.sun = new THREE.DirectionalLight(0xffd6a0,3); this.sun.castShadow=true;
    this.sun.shadow.mapSize.set(2048,2048);
    Object.assign(this.sun.shadow.camera,{left:-radius,right:radius,top:radius,bottom:-radius,near:1,far:150});
    this.sun.shadow.normalBias=.04; this.sun.shadow.bias=-.0003; this.sun.shadow.radius=3;
    scene.add(this.sun); scene.add(this.sun.target);
    // Screen height keeps the blue visible even when the camera looks down.
    scene.background=null;
    this.uniforms={top:{value:new THREE.Color()},bottom:{value:new THREE.Color()},
      height:{value:1}};
    const mat = new THREE.ShaderMaterial({side:THREE.BackSide,depthWrite:false,
      uniforms:this.uniforms,vertexShader:`void main(){gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
      fragmentShader:`uniform vec3 top; uniform vec3 bottom; uniform float height;
        void main(){float h=smoothstep(.08,.95,gl_FragCoord.y/height);
        gl_FragColor=vec4(mix(bottom,top,h),1.);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
        }`});
    this.dome=new THREE.Mesh(new THREE.SphereGeometry(600,24,16),mat);
    this.dome.frustumCulled=false; scene.add(this.dome);
    const rand=seeded('sky_stars'), points=[];
    for(let i=0;i<220;i++) {
      const a=rand()*Math.PI*2, h=.12+rand()*.86, r=Math.sqrt(1-h*h);
      points.push(160*r*Math.cos(a),160*h,160*r*Math.sin(a));
    }
    const geo=new THREE.BufferGeometry(); geo.setAttribute('position',new THREE.Float32BufferAttribute(points,3));
    this.stars=new THREE.Points(geo,new THREE.PointsMaterial({color:0xffe9c1,size:.38,
      transparent:true,depthWrite:false,fog:false})); scene.add(this.stars);
    scene.fog=new THREE.Fog(0xc9d5cc,100,260);
    // A low sea keeps the earth rim visible. Fog softens its distant edge.
    this.water=new THREE.Mesh(new THREE.CircleGeometry(950,96),
      new THREE.MeshStandardMaterial({color:0x529ccd,roughness:.95,metalness:0,
        emissive:0x24628e,emissiveIntensity:.25,transparent:true,depthWrite:false}));
    // Light shallows turn blue before the far sea fades into the sky gradient.
    this.water.material.onBeforeCompile=shader => {
      shader.uniforms.shoreRadius={value:radius};
      shader.vertexShader='varying vec3 seaPosition;\n'+shader.vertexShader.replace(
        '#include <begin_vertex>','#include <begin_vertex>\nseaPosition=position;');
      shader.fragmentShader='uniform float shoreRadius; varying vec3 seaPosition;\n'+shader.fragmentShader.replace(
        '#include <color_fragment>',`#include <color_fragment>
        float depth=smoothstep(shoreRadius,shoreRadius+45.,length(seaPosition.xy));
        diffuseColor.rgb*=mix(vec3(1.45,1.25,1.08),vec3(.65,.85,1.),depth);`).replace(
        // Fade the sea to reveal the sky gradient even at a downward camera angle.
        '#include <opaque_fragment>',`diffuseColor.a*=1.-smoothstep(shoreRadius+70.,shoreRadius+180.,length(seaPosition.xy));
        #include <opaque_fragment>`);
    };
    this.water.rotation.x=-Math.PI/2; this.water.position.y=-2.7; scene.add(this.water);
    // Small round puffs live in the distant sky, never over the village.
    this.clouds=new THREE.Group();
    const scenery=seeded('sky_clouds');
    this.cloudMaterial=new THREE.MeshStandardMaterial({color:0xffffff,flatShading:true,
      emissive:0xffffff,emissiveIntensity:.8,roughness:1,fog:false,toneMapped:false});
    for(let i=0;i<5;i++) {
      const a=i/5*Math.PI*2, center=new THREE.Vector3(Math.cos(a)*380,180+scenery()*35,Math.sin(a)*380);
      for(let j=0;j<5;j++) {
        const puff=new THREE.Mesh(new THREE.IcosahedronGeometry(3+scenery()*2,1),this.cloudMaterial);
        puff.position.copy(center).add(new THREE.Vector3((j-2)*3,scenery()*2,scenery()*3));
        this.clouds.add(puff);
      }
    }
    scene.add(this.clouds);
  }
  setDistance(distance) {
    // Framing varies with aspect ratio; atmosphere must stay behind the island.
    this.scene.fog.near=distance+this.radius*.6;
    this.scene.fog.far=distance+this.radius+120;
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
    const morning=hour>=7 && hour<12;
    const top=light<.1 ? 0x152440 : morning ? 0x82c5ff : light<.65 ? 0x9b758e : 0x8cbad0;
    const bottom=light<.1 ? 0x394663 : morning ? 0xffe6bb : light<.65 ? 0xe6aa79 : 0xe6edfa;
    this.uniforms.top.value.set(top); this.uniforms.bottom.value.set(bottom);
    this.water.material.color.set(light<.1 ? 0x354d65 : 0x529ccd);
    this.scene.fog.color.set(bottom); this.renderer.setClearColor(bottom);
    const angle=(hour-6)/12*Math.PI;
    this.sun.position.set(Math.cos(angle)*42,Math.max(5,Math.sin(angle)*48),20);
    this.sun.color.set(light<.65 ? 0xffbc8b : 0xffe0af); this.sun.intensity=.12+light*3.1;
    this.hemi.intensity=1+light*2; this.stars.material.opacity=night*.9;
    this.lamps.forEach(l => l.intensity=night*7);
  }
  animate(camera) {
    this.uniforms.height.value=this.renderer.domElement.height;
    this.dome.position.copy(camera.position); this.stars.position.copy(camera.position);
    this.clouds.position.copy(camera.position);
  }
}
