// Stable ids from the server drive conversation focus, never names in feed text.
export class WhoPicker {
  constructor() { this.place = null; this.sequence = 0; this.person = ''; }
  sync(s, select) {
    const moved = this.place !== s.you.place.id;
    if (moved) {
      this.place = s.you.place.id;
      this.person = ''; select.value = '';
    }
    const reply = s.reply_to;
    if (reply && reply.sequence > this.sequence) {
      this.sequence = reply.sequence;
      this.person = reply.id;
    }
    return moved;
  }
  apply(select) {
    if ([...select.options].some(o => o.value === this.person)) select.value = this.person;
  }
  choose(id) { this.person = id; }
}
