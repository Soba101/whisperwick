// Browser-independent checks for the boundary between speech and player actions.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source=name => readFileSync(new URL('../whisperwick/web3d/'+name,import.meta.url),'utf8');
const url=text => 'data:text/javascript;base64,'+Buffer.from(text).toString('base64');
const voices=[{voiceURI:'remote',lang:'en-US',localService:false},
  {voiceURI:'local-b',lang:'en-GB',localService:true},
  {voiceURI:'local-a',lang:'en-US',localService:true}];
const spoken=[];
globalThis.window={speechSynthesis:{getVoices:() => voices,addEventListener(){},
  speak:u => spoken.push(u),cancel(){},resume(){}},addEventListener(){}};
globalThis.SpeechSynthesisUtterance=class { constructor(text) { this.text=text; } };
const ttsURL=url(source('tts.js')), sttURL=url(source('stt.js'));
const {TTS}=await import(ttsURL), {STT}=await import(sttURL);
const tts=new TTS(() => {});
tts.add('npc_alice','08:00 The Inn: Alice -> Wren: "Hello, Wren."');
assert.equal(spoken.at(-1).text,'Hello, Wren.');
assert.equal(spoken.at(-1).voice.localService,true);
const identity=tts.identity('npc_alice');
voices.reverse(); assert.equal(tts.identity('npc_alice'),identity);
assert.deepEqual(new TTS(() => {}).identity('npc_alice'),identity);
tts.add('npc_bob','08:00 The Inn: Bob -> Wren: "Second"');
const cancelled=tts.current;
tts.skip(); assert.equal(tts.current.text,'Second');
cancelled.onend(); assert.equal(tts.current.text,'Second');
tts.stop(); assert.equal(tts.current,null); assert.equal(tts.queue.length,0);
tts.add('npc_alice','A narration without quoted speech');
assert.equal(tts.queue.length,0);

const elements=new Map();
function element(id) {
  if(!elements.has(id)) elements.set(id,{value:'',hidden:false,disabled:false,textContent:'',
    parentElement:{hidden:false},maxLength:500,setAttribute(){},addEventListener(){},dispatchEvent(){}});
  return elements.get(id);
}
globalThis.document={getElementById:element,querySelector:() => ({textContent:'Talk'})};
// Storage can be blocked completely, not just return an empty value.
Object.defineProperty(globalThis,'localStorage',{get(){ throw new Error('blocked'); }});
const voiceSource=source('voice.js').replace("'./tts.js'",JSON.stringify(ttsURL))
  .replace("'./stt.js'",JSON.stringify(sttURL));
const {Voice}=await import(url(voiceSource));
const voice=new Voice(); assert.equal(voice.enabled,false);
const line='08:01 The Inn: Alice -> Wren: "New words"';
const state=(feed,total,speech={npc_alice:line}) => ({game_id:'game',you:{place:{id:'loc_inn'}},
  player:{id:'player'},feed,feed_total:total,speech});
voice.update(state([line],1));
element('voice-toggle').onclick(); assert.equal(voice.enabled,true);
voice.update(state([line],1)); assert.equal(voice.tts.current,null);
voice.update(state([line],2)); assert.equal(voice.tts.current.text,'New words');
voice.tts.stop();
voice.update(state(['Narration',line],4,{player:line})); assert.equal(voice.tts.current,null);
voice.update(state([line],5,{})); assert.equal(voice.tts.current,null);
voice.update(state([line],6)); assert.equal(voice.tts.current.text,'New words');
voice.update(state([],6)); assert.equal(voice.tts.queue.length,0);
element('voice-toggle').onclick(); assert.equal(voice.tts.current,null);
voice.update(state([line],7));
element('voice-toggle').onclick();
voice.update(state([line],7)); assert.equal(voice.tts.current,null);
voice.update(state([line],8));
voice.update({...state([],8),you:{place:{id:'loc_market'}}});
assert.equal(voice.tts.current,null);

let inputs=0;
const message=element('message'); message.dispatchEvent=() => inputs++;
const stt=new STT(element('mic'),element('status'),element('fallback'),message,() => {});
stt.setEnabled(true); message.maxLength=5;
stt.fill(' hello world ',''); assert.equal(message.value,'hello'); assert.equal(inputs,1);
stt.fill('changed',''); assert.equal(message.value,'hello');
stt.setEnabled(false); stt.fill('off','hello'); assert.equal(message.value,'hello');
// No submit handlers, fetch or server APIs exist in this harness.
assert.equal(inputs,1);
console.log('Voice boundary checks passed');

// Failed GPU initialization must retry WASM before offering network recognition.
const attempts=[];
Object.defineProperty(globalThis,'navigator',{value:{gpu:{}},configurable:true});
globalThis.testTransformers={env:{backends:{onnx:{wasm:{}}}},pipeline:async (task,model,opts) => {
  attempts.push(opts);
  assert.equal(task,'automatic-speech-recognition');
  assert.equal(model,'onnx-community/whisper-tiny.en');
  if(opts.device==='webgpu') throw new Error('GPU unavailable');
  opts.progress_callback({status:'progress',file:'model.onnx',progress:42});
  return async () => ({text:'local result'});
}};
const modelSource=source('stt.js').replace("import('@huggingface/transformers')",'Promise.resolve(globalThis.testTransformers)');
const {STT:ModelSTT}=await import(url(modelSource));
const local=new ModelSTT(element('mic'),element('status'),element('fallback'),message,() => {});
local.setEnabled(true); await local.load(local.token);
assert.deepEqual(attempts.map(a => a.device),['webgpu','wasm']);
assert.equal(attempts[1].dtype,'q8');
assert.equal(testTransformers.env.backends.onnx.wasm.numThreads,1);
assert.equal(testTransformers.env.useBrowserCache,true);
assert.equal(typeof local.model,'function');
assert.equal(element('fallback').hidden,true);
window.SpeechRecognition=class { constructor() { throw new Error('must require an explicit click'); } };
testTransformers.pipeline=async () => { throw new Error('offline'); };
const failed=new ModelSTT(element('mic'),element('status'),element('fallback'),message,() => {});
await failed.load(failed.token);
assert.match(element('status').textContent,/may send audio to the browser maker/);
assert.equal(element('fallback').hidden,false);
console.log('Whisper loading and fallback checks passed');
