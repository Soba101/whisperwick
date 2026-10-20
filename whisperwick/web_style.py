"""Inline styles for the offline play page. Colours match the 3D page (light parchment)."""

from importlib.resources import files

CSS = """
:root { color-scheme: light; --bg:#e7dbc1; --surface:#f8eed8; --text:#493f32;
  --muted:#6b604e; --line:#c9b89b; --accent:#526b5b; --warn:#a33329;
  --on-accent:#fff8e8; --soft:#e9dfc7; --shadow:0 5px 20px #65533a15;
  --radius:16px; --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s6:24px; }
/* Same parchment palette as the 3D page (2026-10-21), so every page looks like one game.
   The 3D page is light only, so these pages are too.
   Its web fonts stay out: this page is offline. */
* { box-sizing:border-box; }
body { font:15px/1.6 system-ui,sans-serif; background:var(--bg); color:var(--text);
  margin:0; padding:var(--s6); }
body.modal-open { overflow:hidden; }
.report { font-size:13px; min-height:34px; margin-bottom:var(--s3); color:var(--accent); }
.feedback-hint { color:var(--muted); }
.crime-hint { width:100%; margin:var(--s2) 0 0; color:var(--muted); font-size:13px; }
h1,h2,h3 { font-family:Fraunces,"Iowan Old Style",Georgia,serif; line-height:1.2; }
h1 { font-size:32px; margin:0; } h2 { font-size:21px; margin:0 0 var(--s3); }
h3 { font-size:18px; margin:0 0 var(--s2); }
p { margin:0 0 var(--s3); }
/* Cap the width and center it: on a very wide window the two columns stay together. */
.page-head,.wrap { max-width:1200px; margin-inline:auto; }
.page-head { display:flex; flex-wrap:wrap; align-items:center; gap:var(--s3);
  margin-bottom:var(--s6); }
.page-head h1 { margin-right:auto; }
.sub { display:flex; flex-wrap:wrap; gap:var(--s2); width:100%; color:var(--muted); }
.sub span { background:var(--surface); border-radius:var(--radius);
  padding:var(--s1) var(--s3); box-shadow:var(--shadow); }
.sub span:empty { display:none; }
/* The goal stays in view all game, quieter than the title. */
.goal { width:100%; margin:0; color:var(--muted); }
.goal b { color:var(--accent); }
.wrap { display:grid; grid-template-columns:minmax(0, .9fr) minmax(0, 1.1fr);
  gap:var(--s6); }
.wrap > div { min-width:0; }
.card { background:var(--surface); border-radius:var(--radius); padding:var(--s6);
  margin-bottom:var(--s4); box-shadow:var(--shadow); overflow-wrap:anywhere; }
#map { position:relative; aspect-ratio:4/3; background:var(--soft);
  border-radius:var(--radius); box-shadow:var(--shadow); margin-bottom:var(--s4); }
#lines { position:absolute; inset:0; width:100%; height:100%; }
#lines line { stroke:var(--muted); stroke-width:.4; stroke-dasharray:1 1; opacity:.5; }
.place { position:absolute; transform:translate(-50%,-50%); width:42%;
  padding:var(--s2); background:var(--surface); border-radius:var(--radius);
  box-shadow:var(--shadow); }
/* An outline keeps the current place clear without shifting its tokens. */
.place.here { outline:2px solid var(--accent); outline-offset:2px; }
/* Words and borders make exits clear without relying on colour alone. */
.place.can-go { border:2px dashed var(--accent); }
.place.distant { opacity:.45; }
.reach { display:block; font-size:12px; color:var(--accent); }
.place b { display:block; font-size:13px; color:var(--muted); }
.place.here b { color:var(--accent); }
.tok { display:inline-block; margin:var(--s1) var(--s1) 0 0; padding:0 var(--s2);
  font-size:12px; border:1px solid transparent; border-radius:var(--radius);
  background:var(--soft); }
.tok.me { background:var(--accent); color:var(--on-accent); }
.tok.body { color:var(--muted); text-decoration:line-through; border:1px dashed; }
.tok.held { border-color:var(--warn); color:var(--warn); }
.warn { color:var(--warn); }
.notebook-tabs { display:flex; gap:var(--s2); margin-bottom:var(--s4); }
.notebook-tabs [aria-selected="true"] { background:var(--accent); color:var(--on-accent); }
.known-section + .known-section { margin-top:var(--s4); }
.known-row { font-size:13px; padding-block:var(--s1); border-bottom:1px solid var(--line); }
#notes { display:block; width:100%; resize:vertical; margin-block:var(--s2); }
#notes-private { display:block; color:var(--muted); }
#you > div { padding-block:var(--s1); }
#you b { color:var(--muted); font-weight:400; }
#feed { list-style:none; padding:0; margin:0; height:40vh; min-height:200px;
  overflow:auto; line-height:1.75; }
#feed .scene { font-style:italic; }
#feed li { padding:var(--s3) 0; border-bottom:1px solid var(--line); }
/* A plain line instead of a big blank box before anything has happened. */
#feed:empty::before { content:"Nothing seen or heard yet."; color:var(--muted); }
/* Keep status legible even while the feed is scrolled. */
#busy { color:var(--muted); padding-top:var(--s3); font-weight:600; }
#hint { color:var(--muted); margin-bottom:var(--s3); }
.row { display:flex; flex-wrap:wrap; gap:var(--s2); margin-top:var(--s4); }
button,select,input,textarea { font:inherit; min-height:44px; padding:var(--s2) var(--s3);
  border:1px solid var(--line); border-radius:var(--radius); max-width:100%;
  background:var(--surface); color:var(--text); }
button { cursor:pointer; font-weight:600; }
button:hover { background:var(--soft); }
/* Outlines survive both themes and do not rely on colour alone. */
:focus-visible { outline:3px solid var(--accent); outline-offset:3px; }
#send,#close,#again { background:var(--accent); color:var(--on-accent);
  border-color:var(--accent); }
#send:hover,#close:hover,#again:hover { filter:brightness(.92); }
button:disabled,select:disabled,input:disabled { background:var(--soft); color:var(--muted);
  border-color:var(--line); opacity:.6; cursor:not-allowed; filter:none; }
#bar select { margin:0 var(--s1) var(--s2) 0; }
#message { display:block; width:100%; }
/* Who the message goes to, right above the box, so a talk is not sent to the wrong person. */
#talkto { margin:var(--s1) 0 var(--s2); font-weight:600; color:var(--accent); }
#quit { margin-left:auto; color:var(--warn); border-color:var(--warn); }
#reject,#err { margin-top:var(--s3); }
#secretbox { margin-top:var(--s6); padding-top:var(--s4); border-top:1px solid var(--line); }
pre { white-space:pre-wrap; margin:0; font:inherit; }
[hidden] { display:none !important; }
/* Keep legacy section labels available to readers without crowding the guide. */
.sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px;
  overflow:hidden; clip-path:inset(50%); white-space:nowrap; }
@media (max-width:700px) {
  body { padding:var(--s4); } .wrap { grid-template-columns:minmax(0,1fr); }
  .card { padding:var(--s4); } h1 { font-size:28px; }
  /* On a phone the feed and the action bar come right after the map, so playing needs
     no long scroll; You and the notebook follow. The columns dissolve into one list. */
  .wrap { display:flex; flex-direction:column; gap:0; } .wrap > div { display:contents; }
  #map { order:1; } #feedcard { order:2; } #bar, #end { order:3; }
  #youcard { order:4; } #notebook { order:5; } #feed { height:34vh; }
}
@media (max-width:500px) {
  #map { aspect-ratio:1/1; } .place { padding:var(--s1); } .tok { font-size:11px; }
  #quit { margin-left:var(--s4); }
}
"""

# Share ending typography while keeping every 2D asset inline and offline.
CSS += files("whisperwick").joinpath("web3d/ending.css").read_text()

# Tentative words use the same offline page stylesheet.
CSS += "\n#live-talk { overflow-wrap:anywhere; }\n"
