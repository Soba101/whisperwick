"""Offline replay styling and page structure. Run text is filled with textContent."""

CSS = """
:root { --bg:#fafafa; --fg:#1d1d1f; --box:#fff; --line:#999; --muted:#666; --warn:#b3261e; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#161618; --fg:#eee; --box:#222226; --line:#666; --muted:#aaa; --warn:#ff8a80; }
}
body { font: 15px system-ui, sans-serif; background: var(--bg); color: var(--fg);
  margin: 0; padding: 16px; }
h1 { font-size: 18px; margin: 0 0 4px; }
.sub { color: var(--muted); margin-bottom: 12px; }
.wrap { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 700px) { .wrap { grid-template-columns: 1fr; } }
/* Phones: a taller map and narrower boxes, so side boxes stay inside the map. */
@media (max-width: 500px) { #map { aspect-ratio: 1/1; }
  .place { min-width: 0; max-width: 46%; padding: 4px; } .tok { font-size: 11px; } }
#map { position: relative; aspect-ratio: 4/3; border: 1px solid var(--line); border-radius: 8px; }
#lines { position: absolute; inset: 0; width: 100%; height: 100%; }
#lines line { stroke: var(--line); stroke-width: .4; }
.place { position: absolute; transform: translate(-50%,-50%); min-width: 28%; padding: 6px;
  background: var(--box); border: 1px solid var(--line); border-radius: 6px; }
.place b { display: block; font-size: 13px; color: var(--muted); }
.tok { display: inline-block; margin: 2px; padding: 1px 6px; font-size: 13px;
  border: 1px solid var(--fg); border-radius: 10px; }
.tok.body { opacity: .6; text-decoration: line-through; border-style: dashed; }
.tok.held { border-color: var(--warn); color: var(--warn); }
.bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 12px 0; }
#slider { flex: 1 1 100%; }
button, select { font: inherit; padding: 4px 10px; }
#clock { font-weight: 600; min-width: 8em; }
#feed { list-style: none; padding: 0; margin: 0; max-height: 60vh; overflow: auto; }
#feed li { padding: 4px 0; border-bottom: 1px solid var(--line); }
#feed .t { color: var(--muted); font-size: 12px; margin-right: 6px; }
#feed .tag { color: var(--muted); font-size: 12px; }
#feed .arrest { color: var(--warn); }
#feed .thought { font-style: italic; color: var(--muted); }
"""

BODY = """
<h1 id="title">Replay</h1>
<div class="sub">World facts only, replayed from the event log.</div>
<div class="wrap">
  <div>
    <div id="map"><svg id="lines" viewBox="0 0 100 100" preserveAspectRatio="none"></svg></div>
    <div class="bar">
      <input id="slider" type="range" step="1" aria-label="time">
      <button id="prev">Back</button><button id="play">Play</button><button id="next">Step</button>
      <select id="speed" aria-label="speed (game minutes per second)">
        <option value="10">10 min/s</option><option value="30" selected>30 min/s</option>
        <option value="60">60 min/s</option><option value="180">180 min/s</option>
      </select>
      <span id="clock"></span>
    </div>
  </div>
  <div>
    <label id="thoughtbox" hidden><input type="checkbox" id="thoughts">
      Show private thoughts (not world facts)</label>
    <ul id="feed"></ul>
  </div>
</div>
"""

