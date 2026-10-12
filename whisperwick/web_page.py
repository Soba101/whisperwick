"""The play page: one HTML string, inline CSS and JS, no external anything.

It opens offline. Every piece of game text goes in with textContent (see web_js.py),
never innerHTML. The guide says only plain facts about the start: no plot, no hints.
"""

import json

from whisperwick.web_guide import GUIDE, GUIDE_CSS, HINTS
from whisperwick.web_js import JS

# Same tokens as the replay page, so both pages look alike in light and dark.
CSS = """
:root { --bg:#fafafa; --fg:#1d1d1f; --box:#fff; --line:#999; --muted:#666; --warn:#b3261e;
  --accent:#2457c5; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#161618; --fg:#eee; --box:#222226; --line:#666; --muted:#aaa; --warn:#ff8a80;
    --accent:#8ab4ff; }
}
* { box-sizing: border-box; }
body { font: 15px system-ui, sans-serif; background: var(--bg); color: var(--fg);
  margin: 0; padding: 16px; }
h1 { font-size: 18px; margin: 0 0 4px; }
h2 { font-size: 14px; margin: 0 0 6px; color: var(--muted); }
.sub { color: var(--muted); margin-bottom: 12px; }
/* Cap the width and center it: on a very wide window the two columns stay together. */
.wrap { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
body > h1, .sub, .wrap { max-width: 1200px; margin-left: auto; margin-right: auto; }
@media (max-width: 700px) { .wrap { grid-template-columns: 1fr; } }
.card { background: var(--box); border: 1px solid var(--line); border-radius: 8px;
  padding: 10px; margin-bottom: 12px; overflow-wrap: anywhere; }
#map { position: relative; aspect-ratio: 4/3; border: 1px solid var(--line); border-radius: 8px; }
@media (max-width: 500px) { #map { aspect-ratio: 1/1; }
  .place { min-width: 0; max-width: 46%; padding: 4px; } .tok { font-size: 11px; } }
#lines { position: absolute; inset: 0; width: 100%; height: 100%; }
#lines line { stroke: var(--line); stroke-width: .4; }
.place { position: absolute; transform: translate(-50%,-50%); min-width: 28%; padding: 6px;
  background: var(--box); border: 1px solid var(--line); border-radius: 6px; }
.place.here { border: 2px solid var(--accent); }
.place b { display: block; font-size: 13px; color: var(--muted); }
.tok { display: inline-block; margin: 2px; padding: 1px 6px; font-size: 13px;
  border: 1px solid var(--fg); border-radius: 10px; }
.tok.me { background: var(--accent); color: var(--bg); border-color: var(--accent); }
.tok.body { opacity: .6; text-decoration: line-through; border-style: dashed; }
.tok.held, .warn { border-color: var(--warn); color: var(--warn); }
#feed { list-style: none; padding: 0; margin: 0; height: 40vh; overflow: auto; }
#feed li { padding: 4px 0; border-bottom: 1px solid var(--line); }
#busy { color: var(--muted); animation: pulse 1.4s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: .35; } }
.row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
button, select, input { font: inherit; padding: 6px 10px; max-width: 100%; }
#message { flex: 1 1 100%; }
#intro p { margin: 6px 0; }
pre { white-space: pre-wrap; margin: 0; font: inherit; }
[hidden] { display: none !important; }
""" + GUIDE_CSS

BODY = GUIDE + """
<h1>Whisperwick <button id="help" aria-label="How to play">How to play</button></h1>
<div class="sub"><span id="clock"></span> &middot; <span id="where"></span></div>
<div class="wrap">
  <div>
    <div id="map"><svg id="lines" viewBox="0 0 100 100" preserveAspectRatio="none"></svg></div>
    <div class="card" style="margin-top:12px"><h2>You</h2><div id="you"></div></div>
  </div>
  <div>
    <div class="card"><h2>What you see and hear</h2>
      <ul id="feed"></ul><div id="busy" hidden>The villagers are acting...</div></div>
    <div class="card" id="bar">
      <div id="hint"></div>
      <select id="action" aria-label="action"></select>
      <select id="target" aria-label="who or where"></select>
      <select id="item" aria-label="item"></select>
      <input id="message" placeholder="What do you say?" maxlength="500">
      <div class="row"><button id="send">Send</button>
        <button id="w10">Wait 10 min</button><button id="w60">Wait 1 hour</button>
        <button id="quit">Quit</button></div>
      <div id="reject" class="warn" hidden></div>
    </div>
    <div class="card" id="end" hidden><h2>The game is over</h2><pre id="outcome"></pre>
      <div id="secretbox" hidden><h2>Scenario secret (shown only now, not part of the world)</h2>
        <pre id="secret"></pre></div><div id="err" class="warn"></div>
      <div class="row"><button id="again">New game</button></div></div>
  </div>
</div>
"""


def render_page() -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Whisperwick</title><style>{CSS}</style></head><body>{BODY}"
        f"<script>const HINTS = {json.dumps(HINTS)};{JS}</script></body></html>"
    )


def plain_page(text: str) -> str:
    """A bare page with one sentence (no key, or no free seat)."""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Whisperwick</title></head><body><p>{text}</p></body></html>"
    )
