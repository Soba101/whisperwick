// This optional module is loaded only by the 3D voice controls.
// API: https://github.com/hexgrad/kokoro/tree/main/kokoro.js
const model='onnx-community/Kokoro-82M-v1.0-ONNX';
const voices=['af_heart','af_bella','bf_emma','bf_alice','am_adam','am_michael','bm_george','bm_daniel'];
export function kokoroVoice(id) {
  let n=2166136261;
  for(const c of id) n=Math.imul(n^c.charCodeAt(0),16777619);
  return voices[(n>>>0)%voices.length];
}
export class Kokoro {
  constructor(status) { this.status=status; this.token=0; }
  async load() {
    if(this.loading) return this.loading;
    this.loading=(async () => {
      this.status('Downloading Kokoro… Model files are cached by this browser.');
      // The web bundle includes its own compatible Transformers runtime.
      const {KokoroTTS}=await import('https://cdn.jsdelivr.net/npm/kokoro-js@1.2.1/dist/kokoro.web.js');
      const options={dtype:'q8',progress_callback:p => {
        if(p.status==='progress') this.status('Downloading Kokoro: '+(p.file || 'model')+' '+Math.round(p.progress || 0)+'%');
      }};
      const build=device => KokoroTTS.from_pretrained(model,{...options,device});
      if(navigator.gpu) {
        try { this.model=await build('webgpu'); }
        catch { this.model=await build('wasm'); }
      } else this.model=await build('wasm');
      this.status('Kokoro ready. Speech stays on this device.');
      return this.model;
    })();
    return this.loading;
  }
  unlock() {
    // Resume in the tap handler, before downloading or generating audio.
    const Context=window.AudioContext || window.webkitAudioContext;
    if(Context) { this.context ||= new Context(); this.context.resume().catch(() => {}); }
  }
  async speak(id,text,finish,fail) {
    const token=++this.token;
    try {
      const tts=await this.load();
      if(token!==this.token) return;
      const audio=await tts.generate(text,{voice:kokoroVoice(id)});
      if(token!==this.token) return;
      if(!this.context) throw new Error('Audio context unavailable');
      const buffer=this.context.createBuffer(1,audio.audio.length,audio.sampling_rate);
      buffer.copyToChannel(audio.audio,0);
      const source=this.context.createBufferSource(); source.buffer=buffer;
      source.connect(this.context.destination); this.source=source;
      source.onended=() => { if(token===this.token) { this.source=null; finish(); } };
      await this.context.resume();
      if(token===this.token) source.start();
    } catch(error) { if(token===this.token) fail(error); }
  }
  stop() { this.token++; this.source?.stop(); this.source=null; }
}
