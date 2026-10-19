// Whisper downloads model files. Its recorded audio stays in this tab.
export class STT {
  constructor(button,status,fallback,message,quiet) {
    Object.assign(this,{button,status,fallback,message,quiet});
    this.enabled=false; this.token=0; this.phase='idle';
    button.onclick=() => this.tap(); fallback.onclick=() => this.browser();
  }
  say(text) { this.status.textContent=text; }
  setEnabled(enabled) {
    this.enabled=enabled; this.button.hidden=!enabled;
    if(!enabled) { this.cancel(); this.fallback.hidden=true; this.say(''); }
  }
  cancel() {
    this.token++; clearTimeout(this.timer);
    this.recognition?.abort(); this.recognition=null;
    if(this.recorder?.state==='recording') this.recorder.stop();
    this.stream?.getTracks().forEach(t => t.stop()); this.stream=null;
    this.context?.close().catch(() => {}); this.context=null;
    this.phase='idle'; this.button.textContent='Mic'; this.button.setAttribute('aria-pressed','false');
  }
  async load(token) {
    this.phase='loading'; this.say('Downloading Whisper… Model files are cached by this browser.');
    try {
      const {pipeline,env}=await import('@huggingface/transformers');
      env.allowLocalModels=false; env.useBrowserCache=true;
      // A single WASM thread works without cross-origin isolation on Safari.
      env.backends.onnx.wasm.numThreads=1;
      const options={progress_callback:p => {
        if(token!==this.token) return;
        if(p.status==='progress') this.say('Downloading Whisper: '+(p.file || 'model')+' '+Math.round(p.progress || 0)+'%');
      }};
      const build=(device,dtype) => pipeline('automatic-speech-recognition',
        'onnx-community/whisper-tiny.en',{...options,device,dtype});
      // GPU presence alone does not guarantee a compatible adapter or model.
      if(navigator.gpu) {
        try { this.model=await build('webgpu',{encoder_model:'fp32',decoder_model_merged:'q4'}); }
        catch { this.model=await build('wasm','q8'); }
      } else this.model=await build('wasm','q8');
      if(token===this.token) {
        this.fallback.hidden=true;
        this.say('Whisper ready. Tap Mic to record; tap again to stop. Audio stays on this device.');
      }
    } catch {
      if(token!==this.token) return;
      this.say('Whisper could not load. Browser speech recognition may send audio to the browser maker.');
      this.fallback.hidden=!(window.SpeechRecognition || window.webkitSpeechRecognition);
    } finally { if(token===this.token) this.phase='idle'; }
  }
  async tap() {
    if(!this.enabled) return;
    if(this.phase==='recording') { this.recorder.stop(); return; }
    if(this.phase==='browser') { this.recognition.stop(); return; }
    if(this.phase!=='idle') return;
    const token=++this.token;
    if(!this.model) { await this.load(token); return; }
    if(!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      this.say('Microphone recording is unavailable. Use HTTPS or localhost and allow microphone access.'); return;
    }
    this.phase='starting'; this.quiet();
    const original=this.message.value;
    try {
      // Create and resume on the tap, before the permission dialog yields control.
      const Audio=window.AudioContext || window.webkitAudioContext;
      const context=new Audio(); this.context=context; await context.resume();
      if(token!==this.token) return;
      const stream=await navigator.mediaDevices.getUserMedia({audio:true});
      if(token!==this.token) { stream.getTracks().forEach(t => t.stop()); return; }
      this.stream=stream;
      const chunks=[], recorder=new MediaRecorder(stream); this.recorder=recorder;
      recorder.ondataavailable=e => { if(e.data.size) chunks.push(e.data); };
      recorder.onerror=() => {
        if(token===this.token) { this.cancel(); this.say('Recording failed. Please try again.'); }
      };
      recorder.onstop=async () => {
        stream.getTracks().forEach(t => t.stop()); clearTimeout(this.timer);
        if(token!==this.token) return;
        this.phase='transcribing'; this.button.textContent='Mic';
        this.button.setAttribute('aria-pressed','false'); this.say('Transcribing on this device…');
        try {
          const decoded=await context.decodeAudioData(await new Blob(chunks,{type:recorder.mimeType}).arrayBuffer());
          // Mix all channels explicitly, then let Web Audio resample to 16 kHz.
          const Offline=window.OfflineAudioContext || window.webkitOfflineAudioContext;
          const offline=new Offline(1,Math.max(1,Math.ceil(decoded.duration*16000)),16000);
          const mono=offline.createBuffer(1,decoded.length,decoded.sampleRate), data=mono.getChannelData(0);
          for(let c=0;c<decoded.numberOfChannels;c++) {
            const channel=decoded.getChannelData(c);
            for(let i=0;i<data.length;i++) data[i]+=channel[i]/decoded.numberOfChannels;
          }
          const source=offline.createBufferSource(); source.buffer=mono; source.connect(offline.destination); source.start();
          const audio=await offline.startRendering();
          const result=await this.model(audio.getChannelData(0),{chunk_length_s:30,stride_length_s:5});
          if(token===this.token) this.fill(result.text,original);
        } catch { if(token===this.token) this.say('Could not transcribe this recording. Please try again.'); }
        finally {
          await context.close().catch(() => {});
          if(token===this.token) { this.context=null; this.stream=null; this.phase='idle'; }
        }
      };
      recorder.start(); this.phase='recording'; this.button.textContent='Stop mic';
      this.button.setAttribute('aria-pressed','true'); this.say('Recording locally… Tap Stop mic when finished.');
      // Bound memory use on phones. No recording survives switching Voice off.
      this.timer=setTimeout(() => { if(recorder.state==='recording') recorder.stop(); },60000);
    } catch {
      if(token===this.token) { this.cancel(); this.say('Could not open the microphone. Check microphone permission and try again.'); }
    }
  }
  fill(text,original) {
    // A late result must not overwrite typing or a different action's message.
    if(!this.enabled || this.message.disabled || this.message.parentElement.hidden || this.message.value!==original) {
      this.say('Message changed while transcribing. Please record again.'); return;
    }
    const limit=this.message.maxLength;
    this.message.value=limit>=0 ? text.trim().slice(0,limit) : text.trim();
    this.message.dispatchEvent(new Event('input',{bubbles:true}));
    this.say('Dictation ready. Review the message, then press Send.');
  }
  browser() {
    if(!this.enabled || this.phase!=='idle') return;
    const Recognition=window.SpeechRecognition || window.webkitSpeechRecognition;
    if(!Recognition) return;
    // This separate, labelled button is explicit consent to the disclosed fallback.
    const token=++this.token, original=this.message.value;
    const recognition=new Recognition(); this.recognition=recognition; this.quiet();
    recognition.lang='en-US'; recognition.interimResults=false; recognition.continuous=false;
    recognition.onresult=e => { if(token===this.token) this.fill(e.results[0][0].transcript,original); };
    recognition.onerror=() => { if(token===this.token) this.say('Browser speech recognition failed. Please try again.'); };
    recognition.onend=() => { if(token===this.token) { this.phase='idle'; this.recognition=null; this.button.textContent='Mic'; this.button.setAttribute('aria-pressed','false'); } };
    try { recognition.start(); this.phase='browser'; this.button.textContent='Stop mic'; this.button.setAttribute('aria-pressed','true'); this.say('Browser recognition is listening. Audio may be sent to the browser maker.'); }
    catch { this.phase='idle'; this.say('Browser speech recognition could not start.'); }
  }
}
