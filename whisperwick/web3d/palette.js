// Stable colour hashes are only paint. They never influence an intent.
// Shared colours keep the feed and figures consistent without loading WebGL.
export const palette = [0x98705a,0x668271,0xb88269,0x7788a1,0xb39761,0x92739a];
export function clothing(id) {
  return ({npc_hal:0x47668c,npc_victor:0x86619c,npc_alice:0xc78469,
    npc_bob:0x896344,npc_sarah:0x61865c,player:0x4b8581})[id] ?? palette[paintHash(id)%palette.length];
}

function paintHash(id) {
  let n=2166136261;
  for(const c of id) n=Math.imul(n^c.charCodeAt(0),16777619);
  return n>>>0;
}
