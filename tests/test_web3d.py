"""The 3D view uses the same public state and authorization as the original page."""

import json
from pathlib import Path

import pytest
from helpers import fresh_world
from web_helpers import SC, Client, game_server, patch_model, shut

from whisperwick import web3d_assets, web_state
from whisperwick.actions import MAX_MESSAGE_CHARS, Intent
from whisperwick.player_web import WebPlayer


@pytest.fixture
def server(monkeypatch, tmp_path):
    patch_model(monkeypatch)
    server, manager = game_server(tmp_path, 200, key="test-key")
    yield server, manager, Client(server.server_address[1])
    shut(server, manager)


def test_routes_auth_assets_and_shared_state(server):
    _, manager, c = server
    assert c.request('/3d')[0] == 403
    assert c.request('/web3d/scene.js')[0] == 403
    assert c.request('/3d?key=test-key')[0] == 302
    assert c.last.headers['Location'] == '/3d'
    code, html = c.request('/3d')
    assert code == 200 and b'three@0.160.0' in html
    before = c.until(lambda s: s['awaiting'])
    assert c.request('/')[0] == 200
    assert c.state() == before  # Switching views cannot create a second world or expose more.
    assert len(manager.games) == 1
    for name, mime in web3d_assets.ASSETS.items():
        assert c.request('/web3d/' + name)[0] == 200
        assert c.last.headers['Content-Type'] == mime
    assert c.request('/web3d/../player_web.py')[0] == 404
    assert c.request('/web3d/%2e%2e/player_web.py')[0] == 404
    for path in ('/3d', '/web3d/app.js'):
        assert c.request(path, headers={'Host': 'evil.test'})[0] == 403


def test_public_map_has_scenario_links():
    places = {p['id']: p for p in web_state.map_data(SC)}
    assert set(places) == {p.id for p in SC.locations}
    for p in SC.locations:
        assert places[p.id]['links'] == p.links


def test_scene_metadata_only_uses_visible_lines_and_people():
    world, player = fresh_world(), WebPlayer(SC)
    world.act(Intent(actor='npc_bob', action='talk', target='player', message='Visible words'))
    world.npcs['npc_sarah'].location = 'loc_inn'
    assert world.act(Intent(actor='npc_alice', action='talk', target='npc_sarah',
                            message='Hidden words')).ok
    with player.cv:
        player._refresh(world)
    player.waiting_on = 'npc_alice'
    player.turn_of = ('npc_alice', 0, 0, 0)
    s = player.snapshot()
    assert s['message_limit'] == MAX_MESSAGE_CHARS
    assert s['waiting_on'] is None and s['turn_of'] is None
    assert 'Visible words' in s['speech']['npc_bob']
    assert 'Hidden words' not in json.dumps(s)
    for hidden in ('npc_alice', 'item_boots', 'murderer', 'evidence', 'belief'):
        assert hidden not in json.dumps(s)
    assert s['you'] == web_state.you_view(world)
    assert s['actions'] == web_state.actions_for(s['you'])
    player.waiting_on = 'npc_bob'
    assert player.snapshot()['waiting_on'] == 'Bob'
    world.clock.tick = 0
    assert player.snapshot()['daylight'] == 0
    world.clock.tick = 720
    assert player.snapshot()['daylight'] == 1


def test_fixture_is_public_state_and_modules_are_small():
    raw, _ = web3d_assets.asset('fixture_state.json')
    s = json.loads(raw)
    assert s['you']['place']['id'] == 'loc_market'
    assert len(s['actions']) == 7 and s['secret'] is None
    assert s['actions'] == web_state.actions_for(s['you'])
    for hidden in ('item_boots', 'npc_alice', 'murderer', 'evidence'):
        assert hidden not in raw.decode()
    root = Path('whisperwick/web3d')
    for path in root.glob('*.js'):
        text = path.read_text()
        assert len(text.splitlines()) < 200
        assert 'innerHTML' not in text
        assert 'Math.random' not in text
    assert b"fixture" in web3d_assets.asset('app.js')[0]


def test_witnessed_moves_and_custody_are_public_facts_only():
    world, player = fresh_world(), WebPlayer(SC)
    with player.cv:
        player._refresh(world)
    assert world.act(Intent(actor='npc_bob', action='move', target='loc_inn')).ok
    assert world.act(Intent(actor='npc_sarah', action='move', target='loc_inn')).ok
    with player.cv:
        player._refresh(world)
    moves = player.snapshot()['motions']
    assert [m['id'] for m in moves] == ['npc_bob']  # Sarah's walk was out of view.
    assert moves[0]['from'] == 'loc_market' and moves[0]['to'] == 'loc_inn'
    world.npcs['npc_victor'].held_by = 'npc_hal'
    with player.cv:
        player._refresh(world)
    victor = next(p for p in player.snapshot()['you']['people'] if p['id'] == 'npc_victor')
    assert victor['held'] is True
    assert 'holder' not in victor and 'carried' not in victor
