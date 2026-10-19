import {renderEnding} from './ending-content.js';

const node=(tag,text) => {
  const n=document.createElement(tag); n.textContent=text; return n;
};
export class Ending {
  constructor(post) {
    this.post=post;
    this.dialog=node('dialog',''); this.dialog.id='ending3d';
    this.dialog.className='ending-screen';
    this.dialog.setAttribute('aria-label','Your ending');
    document.body.append(this.dialog);
    this.reopen=node('button','View ending'); this.reopen.hidden=true;
    document.querySelector('footer').append(this.reopen);
    this.reopen.onclick=() => this.open();
    this.dialog.oncancel=e => { e.preventDefault(); this.close(); };
  }
  open() {
    if(this.revealed) document.body.classList.add('ending-scene');
    this.dialog.showModal(); this.reopen.hidden=true;
  }
  close() {
    this.dialog.close(); document.body.classList.remove('ending-scene');
    this.reopen.hidden=false; this.reopen.focus();
  }
  update(s) {
    if(s.accusation_pending && !this.picking) {
      this.picking=true;
      const select=node('select',''); select.setAttribute('aria-label','Your accusation');
      select.append(new Option('Nobody',''));
      (s.accusation_choices || []).forEach(p => select.append(new Option(p.name,p.id)));
      const send=node('button','Record and see the ending');
      send.onclick=async () => {
        send.disabled=true;
        try { await this.post('/accuse',{target:select.value || null}); }
        finally { send.disabled=false; }
      };
      this.dialog.append(node('h1','Your accusation'),node('p',
        'Name one person, or nobody. This is your private record; villagers will never see it.'),select,send);
      this.open();
    }
    if(!s.ending_scene || this.revealed) return;
    this.revealed=true; this.dialog.replaceChildren(node('h1','The day is over'));
    const content=node('div',''); content.className='ending-content';
    renderEnding(content,s.ending_scene); this.dialog.append(content);
    if(s.error) this.dialog.append(node('p',s.error));
    const buttons=node('div',''); buttons.className='row';
    const again=node('button','Play again'), close=node('button','Close');
    // Preserve the existing page's New game behavior.
    again.onclick=() => document.getElementById('again').click();
    close.onclick=() => this.close(); buttons.append(again,close); this.dialog.append(buttons);
    document.body.classList.add('ending-scene');
    if(!this.dialog.open) this.open();
    // Replacing the accusation controls also needs a fresh focus destination.
    close.focus();
  }
}
