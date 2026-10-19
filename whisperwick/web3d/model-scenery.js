import * as THREE from 'three';
import {piece,pieces,replaceWith} from './models.js';

export function modelProp(host,pack,name,size,pick) {
  replaceWith(host,() => piece(pack,name,size,[0,0,0],0,pick));
}
export function modelRoad(host,curve) {
  replaceWith(host,async () => {
    const group=new THREE.Group(), count=Math.ceil(curve.getLength()/1.5), jobs=[];
    for(let i=0;i<count;i++) {
      // Arc-length sampling keeps the curved road contiguous at tight bends.
      const u=(i+.5)/count, p=curve.getPointAt(u), t=curve.getTangentAt(u);
      jobs.push(piece('town','road',[1.5,.045,curve.getLength()/count+.1],
        [p.x,.12,p.z],Math.atan2(t.x,t.z)));
    }
    (await pieces(jobs)).forEach(p => group.add(p)); return group;
  });
}
