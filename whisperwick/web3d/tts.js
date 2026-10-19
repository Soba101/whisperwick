// Speech is presentation only. Identity comes from the server's speech map.
function hash(id) {
  let n=2166136261;
  for(const c of id) n=Math.imul(n^c.charCodeAt(0),16777619);
  return n>>>0;
}
export class TTS {
  constructor(change) {
    this.synth=window.speechSynthesis; this.change=change;
    this.queue=[]; this.identities=new Map(); this.current=null;
    this.synth?.addEventListener('voiceschanged',() => this.next());
  }
  unlock() {
    if(!this.synth) return;
    // Safari needs speak() inside a real tap, even with a remembered setting.
    const silent=new SpeechSynthesisUtterance(''); silent.volume=0;
    this.synth.speak(silent); this.synth.resume();
  }
  add(id,line) {
    const first=line.indexOf('"'), last=line.lastIndexOf('"');
    // Never read a prefix or an unquoted narration line.
    if(first<0 || last<=first) return;
    const text=line.slice(first+1,last).trim();
    if(text) this.queue.push({id,text});
    this.next();
  }
  identity(id) {
    if(this.identities.has(id)) return this.identities.get(id);
    const all=this.synth.getVoices();
    if(!all.length) return null;
    const local=all.filter(v => v.localService), pool=local.length ? local : all;
    const english=pool.filter(v => /^en\b/i.test(v.lang));
    const voices=[...(english.length ? english : pool)].sort((a,b) =>
      a.voiceURI<b.voiceURI ? -1 : a.voiceURI>b.voiceURI ? 1 : 0);
    const n=hash(id), identity={voice:voices[n%voices.length],
      pitch:.92+(n%9)*.02,rate:.94+((n>>>8)%7)*.02};
    // Cache the choice so a late voiceschanged event cannot change Alice's voice.
    this.identities.set(id,identity); return identity;
  }
  next() {
    if(!this.synth || this.current || !this.queue.length) { this.changed(); return; }
    const identity=this.identity(this.queue[0].id);
    if(!identity) { this.changed(); return; }
    const {text}=this.queue.shift(), utterance=new SpeechSynthesisUtterance(text);
    Object.assign(utterance,identity); utterance.lang=identity.voice.lang;
    this.current=utterance;
    const finish=() => {
      // cancel() can deliver a late end/error after Skip has started another line.
      if(this.current!==utterance) return;
      this.current=null; this.next();
    };
    utterance.onend=finish; utterance.onerror=finish;
    this.synth.speak(utterance); this.changed();
  }
  changed() { this.change(this.queue.length+(this.current ? 1 : 0)); }
  skip() {
    if(!this.current) this.queue.shift();
    this.current=null; this.synth?.cancel(); this.next();
  }
  stop() {
    this.queue=[]; this.current=null; this.synth?.cancel(); this.changed();
  }
}
