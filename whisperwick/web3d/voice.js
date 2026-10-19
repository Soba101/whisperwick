import {TTS} from './tts.js';
import {STT} from './stt.js';

const $=id => document.getElementById(id), key='whisperwick.voice';
function stored(value) {
  // Private browsing and storage policies must never break the game controls.
  try {
    if(value===undefined) return localStorage.getItem(key)==='on';
    localStorage.setItem(key,value ? 'on' : 'off');
  } catch {} return false;
}
export class Voice {
  constructor() {
    this.enabled=stored(); this.have=null;
    this.tts=new TTS(count => {
      $('voice-skip').disabled=!count; $('voice-stop').disabled=!count;
      $('voice-count').textContent=count ? `${count} speech line${count===1 ? '' : 's'}` : '';
    });
    this.stt=new STT($('mic'),$('voice-status'),$('voice-browser'),$('message'),() => this.tts.stop());
    $('voice-toggle').onclick=() => {
      this.enabled=!this.enabled; stored(this.enabled);
      if(this.enabled) { this.tts.unlock(); $('voice-unlock').hidden=true; }
      this.render();
    };
    // A remembered On still needs a user gesture on iPhone after a reload.
    $('voice-unlock').onclick=() => { this.tts.unlock(); $('voice-unlock').hidden=true; };
    $('voice-skip').onclick=() => { this.tts.unlock(); this.tts.skip(); };
    $('voice-stop').onclick=() => this.tts.stop();
    // UI changes invalidate dictation immediately, before the next state poll.
    $('command').addEventListener('change',() => this.stt.cancel());
    $('command').addEventListener('submit',() => this.stt.cancel());
    $('actions').addEventListener('click',() => this.stt.cancel());
    window.addEventListener('pagehide',() => { this.tts.stop(); this.stt.cancel(); });
    this.render();
  }
  render() {
    $('voice-toggle').textContent='Voice: '+(this.enabled ? 'on' : 'off');
    $('voice-toggle').setAttribute('aria-pressed',String(this.enabled));
    $('voice-tools').hidden=!this.enabled;
    this.stt.setEnabled(this.enabled);
    if(!this.enabled) this.tts.stop();
    else if(!this.tts.synth) this.stt.say('Speech playback is unavailable in this browser.');
  }
  update(s) {
    const place=s.you.place.id;
    // Moving or changing the message action invalidates an in-flight dictation.
    const context=JSON.stringify([place,$('target').value,$('item').value,
      document.querySelector('#actions [aria-pressed="true"]')?.textContent,$('message').disabled,s.finished]);
    if(this.context && this.context!==context) this.stt.cancel();
    this.context=context;
    if(this.place!==place || this.game!==s.game_id) this.tts.stop();
    const initial=this.have===null || this.game!==s.game_id;
    const start=s.feed_total-s.feed.length;
    s.feed.forEach((line,i) => {
      // Skip history, disabled periods and lines outside the server speech map.
      if(initial || start+i<this.have || !this.enabled) return;
      const id=Object.entries(s.speech || {}).find(([,text]) => text===line)?.[0];
      if(id && id!==s.player.id && this.stt.phase==='idle') this.tts.add(id,line);
    });
    this.have=s.feed_total; this.place=place; this.game=s.game_id;
    const visible=!$('message').disabled && !$('message').parentElement.hidden && !s.finished;
    $('mic').hidden=!this.enabled || !visible;
    $('voice-browser').hidden=$('voice-browser').hidden || !visible;
  }
}
