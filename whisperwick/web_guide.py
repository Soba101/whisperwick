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
#intro { position: fixed; inset: 8px; z-index: 5; overflow-y: auto; max-width: 560px;
  margin: 0 auto; }
#intro h2 { color: var(--fg); margin-top: 12px; }
#intro ul { margin: 4px 0; padding-left: 20px; }
#intro button, #bar button, #bar select, #bar input, #help { min-height: 40px; }
#hint { color: var(--muted); margin-bottom: 6px; }
"""

GUIDE = """
<div id="intro" class="card" role="dialog" aria-label="How to play">
  <h1>How to play</h1>
  <h2>Who you are</h2>
  <p>You are Wren, a newcomer who has just arrived in a small village.
    The game starts on day 1 at 08:00 in the Market.</p>
  <h2>What this is</h2>
  <p>The villagers (Alice the innkeeper, Bob the blacksmith, Hal the guard, Sarah the
    priest, Victor the merchant) live their own lives. Each one decides what to say and
    do; nothing is scripted. There is no right way to play: talk to people, listen, go
    places, and see what happens.</p>
  <h2>The screen</h2>
  <ul>
    <li><b>The map</b> shows the four places. People are shown only where you are.</li>
    <li><b>You</b> says where you are, who is here, what is on the ground and what you carry.</li>
    <li><b>What you see and hear</b> lists everything you see and hear, newest at the bottom.</li>
  </ul>
  <h2>Taking a turn</h2>
  <p>1) Pick an action. 2) Pick who or where. 3) For Talk to, type what you say.
    4) Press Send.</p>
  <ul>
    <li><b>Go to:</b> walk to a nearby place.</li>
    <li><b>Talk to:</b> say something to someone here.</li>
    <li><b>Look around:</b> see who and what is here.</li>
    <li><b>Take / Drop:</b> pick up or put down an item.</li>
    <li><b>Give:</b> hand an item to someone here.</li>
    <li><b>Show:</b> show an item to someone, or to everyone here.</li>
  </ul>
  <h2>Time</h2>
  <p>Each action takes a minute of village time. "Wait 10 min" and "Wait 1 hour" let
    time pass while you watch. While the villagers act, the buttons are grey and the line
    at the bottom of the feed says who is busy. Each reply takes a few seconds to think
    up. Villagers sleep from 22:00 to 06:00.</p>
  <h2>The end</h2>
  <p>The game lasts one village day (until 08:00 on day 2), or until you press Quit.
    Then you see what happened, and can press New game.</p>
  <h2>Try first</h2>
  <ul>
    <li>Say hello to someone at the Market and ask about the village.</li>
    <li>Walk to the Inn.</li>
  </ul>
  <button id="close">Start playing</button>
</div>
"""
