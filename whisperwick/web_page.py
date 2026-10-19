"""The play page: one HTML string, inline CSS and JS, no external anything.

It opens offline. Every piece of game text goes in with textContent (see web_js.py),
never innerHTML. The guide says only plain facts about the start: no plot, no hints.
"""

import json

from whisperwick.web_ending import ENDING_HTML, ENDING_JS, ROLE_HTML
from whisperwick.web_guide import GUIDE, GUIDE_CSS, HINTS, HOOK
from whisperwick.web_js import JS
from whisperwick.web_notebook import NOTEBOOK, NOTEBOOK_JS
from whisperwick.web_style import CSS

BODY = ROLE_HTML + GUIDE + f"""
<header class="page-head"><h1>Whisperwick</h1>
<button id="view3d" onclick="location.assign('/3d')">3D view</button>
<button id="help" aria-label="How to play">How to play</button>
<div class="sub"><span id="clock"></span><span id="where"></span></div>
<p class="hook">{HOOK}</p>
<p class="goal"><b>Goal:</b> Find out who killed Mayor Aldric before nightfall,
  or don't: it's your day.</p></header>
<div class="wrap">
  <div>
    <div id="map"><svg id="lines" viewBox="0 0 100 100" preserveAspectRatio="none"></svg></div>
    <div class="card" id="youcard"><h2>You</h2><div id="you"></div></div>
    """ + NOTEBOOK + """
  </div>
  <div>
    <div class="card" id="feedcard"><h2>What you see and hear</h2>
      <ul id="feed"></ul><div id="busy" hidden>The villagers are acting...</div></div>
    <div class="card" id="bar">
      <div id="hint"></div>
      <select id="action" aria-label="action"></select>
      <select id="target" aria-label="who or where"></select>
      <select id="item" aria-label="item"></select>
      <div id="talkto" hidden></div>
      <input id="message" aria-label="What do you say?"
        placeholder="What do you say?" maxlength="500">
      <div class="row"><button id="send">Send</button>
        <button id="w10">Wait 10 min</button><button id="w60">Wait 1 hour</button>
        <button id="quit">Quit</button></div>
      <div id="reject" class="warn" hidden></div>
    </div>
    """ + ENDING_HTML + """
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
        f"<title>Whisperwick</title><style>{CSS}{GUIDE_CSS}</style></head><body>{BODY}"
        f"<script>const HINTS = {json.dumps(HINTS)};{JS}{ENDING_JS}{NOTEBOOK_JS}</script>"
        "</body></html>"
    )


def plain_page(text: str) -> str:
    """A bare page with one sentence (no key, or no free seat)."""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Whisperwick</title></head><body><p>{text}</p></body></html>"
    )
