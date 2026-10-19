"""Serve only packaged view assets. Never turn a request path into a file path."""

from importlib.resources import files

# An allowlist prevents traversal and keeps future private files off the web.
ASSETS = {
    "index.html": "text/html; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "scene.js": "text/javascript; charset=utf-8",
    "palette.js": "text/javascript; charset=utf-8",
    "geometry.js": "text/javascript; charset=utf-8",
    "buildings.js": "text/javascript; charset=utf-8",
    "nature.js": "text/javascript; charset=utf-8",
    "sky.js": "text/javascript; charset=utf-8",
    "characters.js": "text/javascript; charset=utf-8",
    "items.js": "text/javascript; charset=utf-8",
    "labels.js": "text/javascript; charset=utf-8",
    "figures.js": "text/javascript; charset=utf-8",
    "who.js": "text/javascript; charset=utf-8",
    "controls.js": "text/javascript; charset=utf-8",
    "panels.js": "text/javascript; charset=utf-8",
    "voice.js": "text/javascript; charset=utf-8",
    "tts.js": "text/javascript; charset=utf-8",
    "stt.js": "text/javascript; charset=utf-8",
    "fixture_state.json": "application/json",
}

# Exact packaged paths only: no user-controlled filesystem traversal.
CONTENT_TYPES = {".glb": "model/gltf-binary", ".gltf": "model/gltf+json",
                 ".bin": "application/octet-stream", ".png": "image/png"}
for module in ("models", "model-buildings", "model-characters", "model-scenery"):
    ASSETS[module + ".js"] = "text/javascript; charset=utf-8"
MODEL_FILES = (
    "assets/characters/Textures/colormap.png",
    "assets/characters/character-female-a.glb",
    "assets/characters/character-female-b.glb",
    "assets/characters/character-female-c.glb",
    "assets/characters/character-male-a.glb",
    "assets/characters/character-male-b.glb",
    "assets/characters/character-male-c.glb",
    "assets/nature/flower_redA.glb",
    "assets/nature/plant_bush.glb",
    "assets/nature/rock_smallA.glb",
    "assets/nature/tree_oak.glb",
    "assets/nature/tree_pineRoundC.glb",
    "assets/town/Textures/colormap.png",
    "assets/town/banner-green.glb",
    "assets/town/banner-red.glb",
    "assets/town/cart.glb",
    "assets/town/chimney.glb",
    "assets/town/fence.glb",
    "assets/town/fountain-center.glb",
    "assets/town/fountain-round.glb",
    "assets/town/hedge.glb",
    "assets/town/lantern.glb",
    "assets/town/road.glb",
    "assets/town/roof-gable.glb",
    "assets/town/roof-high-point.glb",
    "assets/town/stall-green.glb",
    "assets/town/stall-red.glb",
    "assets/town/stall-stool.glb",
    "assets/town/stall.glb",
    "assets/town/wall-arch.glb",
    "assets/town/wall-door.glb",
    "assets/town/wall-window-glass.glb",
    "assets/town/wall-window-round.glb",
    "assets/town/wall-wood-door.glb",
    "assets/town/wall-wood-window-glass.glb",
    "assets/town/wall-wood.glb",
    "assets/town/wall.glb",
)
for name in MODEL_FILES:
    ASSETS[name] = CONTENT_TYPES["." + name.rsplit(".", 1)[1]]


def asset(name: str) -> tuple[bytes, str] | None:
    if name not in ASSETS:
        return None
    return files("whisperwick").joinpath("web3d", name).read_bytes(), ASSETS[name]
