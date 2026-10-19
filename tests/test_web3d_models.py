"""Selected art must be self-contained, served safely, and remain presentation only."""

import json
import struct
from pathlib import Path, PurePosixPath

from helpers import fresh_world
from test_web3d_routes import request
from web_helpers import SC

from whisperwick import web3d_assets
from whisperwick.player_web import WebPlayer


def glb_document(name):
    raw, mime = web3d_assets.asset(name)
    assert mime == 'model/gltf-binary' and raw[:4] == b'glTF'
    length, kind = struct.unpack_from('<II', raw, 12)
    assert kind == 0x4E4F534A
    return json.loads(raw[20:20 + length])


def test_selected_models_are_small_and_all_dependencies_are_served():
    root = Path('whisperwick/web3d/assets')
    assert sum(p.stat().st_size for p in root.rglob('*') if p.is_file()) < 20_000_000
    actual = {str(p.relative_to(root.parent)) for p in root.rglob('*')
              if p.suffix in web3d_assets.CONTENT_TYPES}
    assert actual == set(web3d_assets.MODEL_FILES)
    for name in actual:
        response = request('/web3d/' + name)
        assert response['code'] == 200
        assert response['headers']['Content-Type'] == web3d_assets.ASSETS[name]
        if not name.endswith('.glb'):
            continue
        document = glb_document(name)
        for entry in document.get('images', []) + document.get('buffers', []):
            if uri := entry.get('uri'):
                dependency = str(PurePosixPath(name).parent / uri)
                assert dependency in actual
                assert request('/web3d/' + dependency)['code'] == 200


def test_animated_models_have_required_clips():
    for name in web3d_assets.MODEL_FILES:
        if not name.startswith('assets/characters/character-'):
            continue
        clips = {a['name'] for a in glb_document(name)['animations']}
        assert {'idle', 'walk', 'interact-right', 'sit', 'emote-yes', 'emote-no'} <= clips


def test_model_routes_share_auth_and_reject_traversal():
    name = '/web3d/assets/town/road.glb'
    assert request(name, authorized=False)['code'] == 403
    assert request(name, host=False)['code'] == 403
    for path in ('../player_web.py', 'assets/../../../.env',
                 'assets/town/../../../../.env', 'assets/town/%2e%2e/road.glb',
                 '/assets/town/road.glb', 'assets-src/License.txt'):
        assert web3d_assets.asset(path) is None
        assert request('/web3d/' + path)['code'] == 404


def test_gestures_only_follow_witnessed_successful_events():
    world, player = fresh_world(), WebPlayer(SC)
    with player.cv:
        player._refresh(world)
    assert player.snapshot()['interactions'] == []
    assert not world.act({'actor': 'npc_bob', 'action': 'take', 'item': 'missing'}).ok
    # Hal's item handling is outside Wren's view. Victor's is witnessed at the market.
    assert world.act({'actor': 'npc_hal', 'action': 'take', 'item': 'item_knife'}).ok
    assert world.act({'actor': 'npc_victor', 'action': 'show', 'item': 'item_boots'}).ok
    with player.cv:
        player._refresh(world)
    gestures = player.snapshot()['interactions']
    assert len(gestures) == 1 and gestures[0]['id'] == 'npc_victor'
    assert set(gestures[0]) == {'id', 'sequence'}  # No item or private inventory leaks.
    with player.cv:
        player._refresh(world)
    assert player.snapshot()['interactions'] == gestures
    assert world.act({'actor': 'npc_victor', 'action': 'give', 'item': 'item_boots',
                      'target': 'npc_bob'}).ok
    with player.cv:
        player._refresh(world)
    assert player.snapshot()['interactions'][0]['sequence'] > gestures[0]['sequence']
    assert world.move('npc_victor', 'loc_inn').ok
    with player.cv:
        player._refresh(world)
    assert player.snapshot()['interactions'] == []
