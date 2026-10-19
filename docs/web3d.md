# Whisperwick browser village

Built for issue #96: `/3d` adds a three.js village beside the existing `/` page.
Both pages share the same game cookie, `/state`, and action endpoints. The browser
renders public facts and submits intentions; Python still validates every action.
The model pass changes presentation only; no engine or visibility rules changed.
Selected CC0 Kenney art totals about 2 MB; the unpacked `assets-src/` is ignored.

## The diorama

Places are laid out from sorted stable IDs, with curved dirt ribbons following
scenario links. The round island has a dirt rim and gently displaced, vertex-coloured
grass. Place IDs select recipes assembled from Fantasy Town Kit walls, doors, windows,
roofs and chimneys: a two-storey timber inn with smoke and a banner sign, four
market stalls around a fountain with a cart and stools, a tall stone temple with
arches, round windows and pointed roof, and a stone hall with banners, a clock,
flag and barred cell. Unknown IDs get a cottage with a stable roof tint. Pack pieces
are fitted in local axes before rotation, so walls meet at corners. Warm window
panes follow server daylight. Linked places have curved roads made from town road
tiles; walking follows the same curves. Buildings and entrances face the island centre. Nature Kit trees, bushes, flowers and rocks,
and town fences/hedges use seeds from place IDs. Entrances and paths stay clear.
Small seeded groves fill gaps between places, with more bushes, flowers and rocks.
Short fences and lamps line clear sections of the paths. The central code-built well remains.

The renderer uses antialiasing, sRGB output, ACES filmic tone mapping, pixel ratio
capped at two, and soft shadows. One directional sun casts shadows, with hemisphere
fill. The server clock and daylight drive a gradient sky, matching horizon fog,
sun position, blue-gold mornings, dawn/dusk colours, night stars, and warm point
lights by windows and path lamps. A blue sea below the earth rim has lighter shallows and fades only in the distance.
Small white sphere clusters stay high and far from the camera. The screen-height sky
gradient stays blue above a pale gold morning horizon; fog shares the horizon colour.
Atmosphere follows camera framing. Smoke, breathing, walking bounce, candle flicker and camera glides are
cosmetic and never sent to the server.

Mini Characters have a fixed, distinct model for each known villager ID and Wren.
Hal keeps a blue guard helmet, Victor a purple hat, Alice an apron, Bob brown,
Sarah green, and Wren a teal cloak and glow ring. Figures are enlarged 1.6 times
and stand in spaced arcs near the inward-facing doors, facing the camera when idle.
Extra rows and a rim margin keep crowded groups on the island. Unknown IDs choose a stable model.
Every animated instance uses SkeletonUtils.clone, its own mixer and cloned materials;
geometry and textures belong to the shared model cache. Held people are desaturated
and idle at the Town Hall cell spot. Bodies retain their public body styling.

Characters play idle when standing and walk during witnessed motion. Server-reported
waiting puts Wren in sit; explicit person waiting/sleeping fields also use sit.
Give/take/show use interact-right only after successful engine events accepted by
the existing visible-feed filter. Polling never restarts the same gesture; initial
snapshots do not replay old gestures. No gesture exposes an item ID or inventory.
Emote-yes/no are never selected or interpreted as agreement. Visible speakers face
a visible neighbour as a cosmetic pose. Ground lanterns and carts use town models;
mugs, bread, coins, candles, knives and generic crates keep their code-built shapes.

All model loads are cached once, including failures. Scenery clones the cached
scene; characters clone the skeleton. Replacement waits for a whole recipe to load.
Failed models or textures leave the polish pass's code-built props in place.
Nature materials use nonmetallic bark, rocks and foliage: their embedded colours
need diffuse lighting rather than a missing environment reflection. Foliage is
slightly lighter, with brighter blue-sky hemisphere fill for morning shadows. Removing
a figure during loading safely discards the late clone without disposing cache-owned
geometry or textures. No model load changes server state.

HTML place labels get first choice of clear screen positions; other labels stack
into remaining slots, shifting horizontally when vertical slots are crowded. Names
stay visible at village zoom, with colour dots and a bold starred player pill. Place
labels are larger too; labels hide only outside the view or when no clear slot fits.
Speech bubbles extract only the quoted words from feed lines, have tails, show at
most 80 characters with an ellipsis, and fade over
6.5 seconds; repeated polling of the same speech does not restart the timer. The
full text remains in the expandable feed. Feed dots use the figure's colour when
the line matches server-tagged speech, otherwise a neutral colour. No speaker ID is
inferred from display names. NPC inventories stay private; hovering/clicking Wren
lists her carried items.

The initial camera looks down about 38 degrees and fits the projected island rim
to roughly 90% of the viewport width, with vertical clearance for tall buildings.
Resize recomputes the framing, including phone widths. Loading and player moves
ease the target slightly toward the player’s place; cursor-directed zoom reaches
individual buildings with a minimum distance of 2.5 scene units. Orbit is damped
and limited above ground; clicking a place glides the camera and submits a move
only when the server offers that destination. Follow tracks Wren smoothly. The HUD
uses parchment/wood colours, rounded panels, Google Fonts (Fraunces and DM Sans,
with local fallbacks), and visible focus/disabled states with reason tooltips.
The seven server-described actions, message limit, waits, quit/new game, clock,
hook, feed, sightings and notes remain available. Information panels use tabs,
with a compact stacked layout at phone width. Notes share the 2D per-game key.

Fallback geometry is merged by material. Model meshes retain their UVs and shared
geometry; each selectable clone receives the same stable pick ID. Only the sun
casts shadows; lamp lights have short ranges. The target is fewer than about 300
draw calls and 60 fps on a laptop, but neither is measured in this environment.

## Run and preview

```sh
uv run whisperwick play --web
# Open http://127.0.0.1:8000/3d
uv run whisperwick play --web --scenario scenarios/murder_of_the_mayor_goods.yaml
```

For a keyed server, open `/3d?key=YOUR_KEY` first. Pages and assets share Host/key
checks. Static assets use an explicit allowlist, including every scene module.
three.js, OrbitControls, BufferGeometryUtils, GLTFLoader and SkeletonUtils load from
jsDelivr at pinned version 0.160.0; there is no npm or build step. Selected models
and their colormaps are packaged locally under `web3d/assets/`. The Nature Kit uses
material colours and supplies no colormap. See `assets/LICENSES.md` and the original
pack licenses for Kenney attribution and CC0 1.0. If the CDN or WebGL fails, the HUD remains available and links
to the 2D page. The font download is optional.

Open `/3d?fixture=1` for a public goods-scenario snapshot without a model, new game,
or posted actions. To preview without the game server:

```sh
python3 -m http.server 8001 --bind 127.0.0.1 --directory whisperwick
# Open http://127.0.0.1:8001/web3d/index.html?fixture=1
```

The fixture still needs CDN access and WebGL. It contains no private inventories
or plot secrets and supplies all seven server action descriptions.

## Optional voice (issue #101)

Voice starts off. The header toggle remembers its setting in browser localStorage;
blocked storage leaves the controls usable. A toggle tap unlocks Safari audio.
After reloading with Voice on, tap Enable audio if playback needs another gesture.
Skip advances one speech line; Stop clears playback until new lines arrive.
Only new, quoted feed lines matched exactly to the server speech map are spoken.
Wren's lines, initial history and narration stay silent. Moving clears the queue.
Stable villager IDs choose cached voices, pitch and rate; local voices get priority.
Voice availability depends on installed voices, and nonlocal voices can use the
browser's speech service when no local voices exist.

Tap Mic to download Whisper the first time, then tap again to record. Tap Stop mic
to transcribe; recordings also stop after one minute. Whisper uses the pinned
Transformers.js 3.0.2 import from jsDelivr and onnx-community/whisper-tiny.en from
Hugging Face. Model files use the browser cache. WebGPU is tried first, with
single-threaded WASM as fallback. Audio is decoded, mixed to mono and resampled to
16 kHz locally. Microphone access requires HTTPS or localhost and permission.
Review the resulting text and press Send yourself. Dictation never submits actions.
Changing action/target, moving or disabling Voice discards pending dictation.
If the model cannot load, a separate browser-recognition button appears only
alongside a warning that it may send audio to the browser maker.

`node tests/web3d_voice.mjs` checks filtering, stable voice selection, cancellation
and message-only dictation using browser mocks. The socket-free route tests check
the new assets, authentication and the unchanged external-link-free 2D page.
Real iPhone Safari and desktop browser checks remain manual: first-tap audio unlock,
installed voices, Skip/Stop, microphone permission, recording codecs, model download
progress/cache, WebGPU/WASM inference, and the disclosed browser fallback.

## Files

- `index.html`, `style.css`: responsive parchment HUD and scene container.
- `app.js`: state polling and existing action endpoints, including fixture mode.
- `scene.js`: composition, renderer, deterministic layout, picking and camera.
- `geometry.js`, `palette.js`: chamfered primitives, batching, seeds and colours.
- `buildings.js`, `nature.js`, `sky.js`: buildings, island, paths, dressing and light.
- `characters.js`, `items.js`, `figures.js`: fallback props, public figures and motion.
- `models.js`: shared loader/cache, safe cloning, fitting, disposal and fallback swap.
- `model-buildings.js`, `model-scenery.js`: modular recipes, roads and seeded art.
- `model-characters.js`: stable identities, accessories, skeletons and animation.
- `assets/`: only used GLBs, referenced colormaps and original CC0 licenses.
- `labels.js`: screen collision placement, coloured name pills and timed bubbles.
- `controls.js`, `panels.js`: server action choices, feed, sightings and private notes.
- `voice.js`, `tts.js`, `stt.js`: optional browser speech and message-only dictation.
- `web3d_assets.py`: asset allowlist; `web_scene.py`: public presentation metadata.

Every JavaScript module is below 200 lines. Speech and motion metadata use the
existing visible-event filter. No route finding, game rules, hints or model calls
live in JavaScript.

## Validation and remaining checks

`UV_CACHE_DIR=/tmp/whisperwick-uv uv run ruff check .` passes. All JavaScript modules
pass `node --check`. The full pytest run has 691 passed and one skipped; 11 failures
and one setup error all come from sandbox restrictions on binding local sockets.
A follow-up run excluding only the 12 socket-dependent tests passes
(691 passed, one skipped, 12 deselected). A Node collision check places 12 crowded
labels without overlaps at 412×372 and 355×280 scene sizes (from the previous pass).
A pass-3 Node check verifies speech prefix removal, 80-character trimming, full
speech titles, plain speech and unchanged timers on repeated polling. The socket-free tests
include asset size, GLB structure, texture dependencies,
character clips, route MIME types, auth/traversal, visibility, and witnessed gestures.
The cache override avoids the read-only default UV cache directory. Assets remain
about 2 MB; this look pass adds no files to the asset packs.

Browser rendering, 375 px layout, draw calls/FPS and a live-model game remain manual
checks: this sandbox cannot bind a localhost preview server. On an unrestricted
machine, open fixture mode at 800×600 and 375 px, inspect names and sky at 08:00,
check day/night windows, orbit/focus/zoom, then walk, talk and take/drop/give/show in
the goods scenario. Block a model or its texture in browser devtools and reload to
check the corresponding procedural fallback. Check held figures behind the cell
bars and repeated polling without gesture replay. No commit was made.
