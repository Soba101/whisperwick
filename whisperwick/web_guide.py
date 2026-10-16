"""The "How to play" guide and the hint line. Plain facts about the controls only.

Nothing here says what will happen or what to look for: the villagers decide for
themselves. The words are fixed text, so the page needs no model and no network.
"""

# Shown just above the action bar. The page script picks one by state.
HINTS = {
    "turn": "Your turn: choose what Wren does, then press Send.",
    "busy": "The villagers are acting. Wait a moment...",
    "auto": "Waiting for a reply...",
    "message": "Type what you want to say.",
}

GUIDE_CSS = """
/* The overlay fills the viewport; the card only takes the space its content needs. */
#intro { position:fixed; inset:0; z-index:5; display:flex; align-items:center;
  justify-content:center; padding:var(--s4); background:#10191299;
  backdrop-filter:blur(4px); }
.guide-card { width:100%; max-width:640px; max-height:88vh; max-height:88dvh;
  display:flex; flex-direction:column; background:var(--surface);
  border-radius:var(--radius); box-shadow:0 16px 64px #0005; overflow:hidden; }
.guide-content { overflow-y:auto; padding:var(--s6); min-height:0; }
.guide-head { display:flex; align-items:center; gap:var(--s3); margin-bottom:var(--s3); }
.guide-head h1 { flex:1; font-size:28px; }
/* The soft goal stands out so a new player knows why to talk to people. */
.goal-box { padding:var(--s3) var(--s4); border-left:4px solid var(--accent);
  background:var(--soft); border-radius:var(--radius); }
.goal-box b { display:block; color:var(--accent); }
#dismiss { font-size:24px; line-height:1; padding:var(--s2); min-width:44px; }
#intro h2 { margin:var(--s6) 0 var(--s3); }
#intro p { margin:0 0 var(--s3); }
.villagers { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:var(--s2); }
.villager { text-align:center; background:var(--soft); padding:var(--s3) var(--s1);
  border-radius:var(--radius); font-size:12px; }
.villager b,.villager span { display:block; }
.initial { display:grid; place-items:center; width:32px; height:32px; margin:0 auto var(--s2);
  border-radius:50%; background:var(--surface); color:var(--accent); font-weight:700; }
.steps,.actions,.info { display:grid; grid-template-columns:repeat(2,minmax(0,1fr));
  gap:var(--s2); }
.steps { list-style:none; padding:0; counter-reset:step; margin:0; }
.steps li,.actions > div,.info > div { padding:var(--s3); background:var(--soft);
  border-radius:var(--radius); }
.steps li { counter-increment:step; }
.steps li::before { content:counter(step); display:inline-grid; place-items:center;
  width:24px; height:24px; margin-right:var(--s2); background:var(--accent);
  color:var(--on-accent); border-radius:50%; font-weight:700; }
.actions b { display:block; } .actions,.info { font-size:14px; }
.info { margin-top:var(--s6); } #intro .info h2 { margin-top:0; }
#intro .info p { margin:0; }
.screen-row { font-size:13px; color:var(--muted); }
.screen-row p { border-bottom:1px solid var(--line); padding-bottom:var(--s2); }
#intro ul { margin:0; padding-left:var(--s6); }
/* A separate flex footer stays reachable while the guide content scrolls. */
.guide-footer { flex-shrink:0; padding:var(--s3) var(--s6); border-top:1px solid var(--line);
  background:var(--surface); display:flex; justify-content:flex-end; }
@media (max-width:500px) {
  .guide-content { padding:var(--s4); } .villagers { grid-template-columns:repeat(3,1fr); }
  .info,.steps { grid-template-columns:1fr; } .actions { font-size:13px; }
}
"""

GUIDE = """
<div id="intro" role="dialog" aria-modal="true" aria-labelledby="guide-title">
 <div class="guide-card">
  <div class="guide-content">
   <div class="guide-head"><h1 id="guide-title">How to play</h1>
    <button id="dismiss" aria-label="Close How to play">&times;</button></div>
   <h2 class="sr-only">Who you are</h2>
   <p>You are Wren, a newcomer who has just arrived in a small village.
    The game starts on day 1 at 08:00 in the Market.</p>
   <p class="goal-box"><b>Your goal</b> Find out what is going on in the village.</p>
   <h2 class="sr-only">What this is</h2>
   <h2>The villagers</h2>
   <div class="villagers">
    <div class="villager"><div class="initial" aria-hidden="true">A</div>
     <b>Alice</b><span>innkeeper</span></div>
    <div class="villager"><div class="initial" aria-hidden="true">B</div>
     <b>Bob</b><span>blacksmith</span></div>
    <div class="villager"><div class="initial" aria-hidden="true">H</div>
     <b>Hal</b><span>guard</span></div>
    <div class="villager"><div class="initial" aria-hidden="true">S</div>
     <b>Sarah</b><span>priest</span></div>
    <div class="villager"><div class="initial" aria-hidden="true">V</div>
     <b>Victor</b><span>merchant</span></div>
   </div>
   <p>The villagers live their own lives. Each one decides what to say and
    do; nothing is scripted. There is no right way to play: talk to people, listen, go
    places, and see what happens.</p>
   <h2 class="sr-only">Taking a turn</h2>
   <h2>A turn in four steps</h2>
   <ol class="steps"><li>Pick an action.</li><li>Pick who or where.</li>
    <li>For Talk to, type what you say.</li><li>Press Send.</li></ol>
   <h2>Actions</h2>
   <div class="actions">
    <div><b>Go to</b>Walk to a nearby place.</div>
    <div><b>Talk to</b>Say something to someone here.</div>
    <div><b>Look around</b>See who and what is here.</div>
    <div><b>Take / Drop</b>Pick up or put down an item.</div>
    <div><b>Give</b>Hand an item to someone here.</div>
    <div><b>Show</b>Show an item to someone, or to everyone here.</div>
   </div>
   <div class="info">
    <div><h2>Time</h2>
     <p>Each action takes a minute of village time. "Wait 10 min" and "Wait 1 hour" let
      time pass while you watch. While the villagers act, the buttons are grey and the line
      at the bottom of the feed says who is busy. Each reply takes a few seconds to think
      up. Villagers sleep from 22:00 to 06:00.</p></div>
    <div><h2>The end</h2>
     <p>The game lasts one village day (until 08:00 on day 2), or until you press Quit.
      Then you see what happened, and can press New game.</p></div>
   </div>
   <h2>The screen</h2>
   <div class="screen-row">
    <p><b>The map</b> shows the four places. People are shown only where you are.
     Places you can walk to from where you are are marked on the map.</p>
    <p><b>You</b> says where you are, who is here, what is on the ground and what you carry.</p>
    <p><b>What you see and hear</b> lists everything you see and hear, newest at the bottom.</p>
   </div>
   <h2>Try first</h2>
   <ul><li>Say hello to someone at the Market and ask about the village.</li>
    <li>Walk to the Inn.</li></ul>
  </div>
  <div class="guide-footer"><button id="close">Start playing</button></div>
 </div>
</div>
"""
