// A closing tableau is presentation only. It never moves anyone in the world.
export function endingCamera(v) {
  const hall='loc_town_hall';
  if(!v.spots.has(hall)) return;
  v.follow=false; v.goal=null;
  const held=[...v.figures.rows.values()].filter(r => r.record.held);
  const target=v.local(hall,2.3,2,3.1);
  // Widen the frame for crowded cells and narrow phone viewports.
  const spread=Math.max(8,held.length*1.5);
  const distance=Math.max(14,spread/Math.max(.35,v.camera.aspect));
  const position=v.local(hall,2.3,2+distance*.45,3.1+distance);
  v.endingShot={target,position};
  v.sky.setDistance(distance);
}
export function glideEnding(v,dt) {
  if(!v.endingShot) return false;
  const ease=matchMedia('(prefers-reduced-motion: reduce)').matches ? 1 : 1-Math.exp(-dt*1.6);
  v.controls.target.lerp(v.endingShot.target,ease);
  v.camera.position.lerp(v.endingShot.position,ease);
  return true;
}
