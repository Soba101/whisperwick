// Use a tiny model stand-in to verify loading, playback, and stale async work.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../whisperwick/web3d/kokoro.js',import.meta.url),'utf8');
const attempts=[], voices=[], nodes=[], status=[];
let resume=0, failAll=false, resolveAudio;
const audio={audio:new Float32Array([0,.5,0]),sampling_rate:24000};
Object.defineProperty(globalThis,'navigator',{value:{gpu:{}},configurable:true});
globalThis.window={AudioContext:class {
  constructor() { this.destination={}; }
  resume() { resume++; return Promise.resolve(); }
  createBuffer(channels,length,rate) {
    assert.equal(channels,1); assert.equal(length,3); assert.equal(rate,24000);
    return {copyToChannel(data) { assert.equal(data,audio.audio); }};
  }
  createBufferSource() {
    const node={connect(){},start(){this.started=true;},stop(){this.stopped=true;}};
    nodes.push(node); return node;
  }
}};
globalThis.testKokoro={KokoroTTS:{async from_pretrained(model,options) {
  assert.equal(model,'onnx-community/Kokoro-82M-v1.0-ONNX');
  attempts.push(options);
  if(options.device==='webgpu' || failAll) throw new Error('no GPU');
  options.progress_callback({status:'progress',file:'model.onnx',progress:42});
  return {generate:async (text,options) => {
    voices.push(options.voice);
    assert.equal(text,'Hello.');
    return resolveAudio ? new Promise(resolve => { resolveAudio=resolve; }) : audio;
  }};
}}};
const transformed=source.replace(/import\('https:\/\/cdn.jsdelivr.net\/npm\/kokoro-js@1\.2\.1\/dist\/kokoro.web.js'\)/,
  'Promise.resolve(globalThis.testKokoro)');
assert.notEqual(source,transformed); // The pinned import itself is part of the check.
const {Kokoro,kokoroVoice}=await import('data:text/javascript;base64,'+Buffer.from(transformed).toString('base64'));
const kokoro=new Kokoro(text => status.push(text));
kokoro.unlock(); assert.equal(resume,1);
await kokoro.load(); await kokoro.load();
assert.deepEqual(attempts.map(a => a.device),['webgpu','wasm']);
assert.ok(attempts.every(a => a.dtype==='q8'));
assert.ok(status.some(s => s.includes('42%')));
assert.equal(kokoroVoice('npc_alice'),kokoroVoice('npc_alice'));
let finished=0;
await kokoro.speak('npc_alice','Hello.',() => finished++,assert.fail);
assert.equal(nodes.at(-1).started,true);
assert.equal(voices.at(-1),kokoroVoice('npc_alice'));
nodes.at(-1).onended(); assert.equal(finished,1);
// Stop while inference is pending must prevent playback after inference resolves.
resolveAudio=true;
const pending=kokoro.speak('npc_bob','Hello.',assert.fail,assert.fail);
await new Promise(resolve => setTimeout(resolve,0));
assert.equal(typeof resolveAudio,'function');
const count=nodes.length; kokoro.stop(); resolveAudio(audio); await pending;
assert.equal(nodes.length,count);
failAll=true;
await assert.rejects(new Kokoro(() => {}).load());
console.log('Kokoro loading, stable identity and cancellation checks passed');
