"""Exercise real handler branches without sockets (also works in a restricted sandbox)."""

import json
from http.cookies import SimpleCookie
from io import BytesIO
from types import SimpleNamespace

from helpers import fresh_world
from web_helpers import SC

from whisperwick.player_web import WebPlayer
from whisperwick.web_server import Handler


def request(path, *, authorized=True, host=True, token='seat'):
    player = WebPlayer(SC)
    with player.cv:
        player._refresh(fresh_world())
    game = SimpleNamespace(token='seat', player=player)
    handler = object.__new__(Handler)
    handler.path = path
    handler.key = 'key'
    handler.host_ok = lambda: host
    handler.key_cookie_ok = lambda: authorized
    handler.secure = lambda: False
    handler.cookies = lambda: {'ww_game': token}
    handler.games = SimpleNamespace(open=lambda t: game, get=lambda t: game, choose_roles=False)
    handler.headers = {}
    handler.wfile = BytesIO()
    result = {'headers': {}}
    handler.send_response = lambda code: result.update(code=code)
    handler.send_header = lambda k, v: result['headers'].update({k: v})
    handler.end_headers = lambda: None
    handler.do_GET()
    result['body'] = handler.wfile.getvalue()
    return result


def test_pages_share_identical_visible_state_and_seat():
    for path in ('/', '/3d'):
        r = request(path, token=None)
        assert r['code'] == 200
        cookie = SimpleCookie(r['headers']['Set-Cookie'])
        assert cookie['ww_game'].value == 'seat'
    s = json.loads(request('/state')['body'])
    assert s['you'] == json.loads(request('/state')['body'])['you']
    assert s['secret'] is None
    for hidden in ('npc_alice', 'item_boots', 'murderer', 'belief'):
        assert hidden not in request('/state')['body'].decode()


def test_auth_checks_cover_pages_and_assets():
    for path in ('/3d', '/web3d/scene.js', '/web3d/fixture_state.json'):
        assert request(path, authorized=False)['code'] == 403
        assert request(path, host=False)['code'] == 403
    redirect = request('/3d?key=key', authorized=False)
    assert redirect['code'] == 302 and redirect['headers']['Location'] == '/3d'
    assert 'HttpOnly' in redirect['headers']['Set-Cookie']
    fixture = request('/3d?fixture=1')
    assert fixture['code'] == 200 and 'Set-Cookie' not in fixture['headers']
    assert request('/web3d/scene.js')['headers']['Content-Type'].startswith('text/javascript')
    for path in ('/web3d/../player_web.py', '/web3d/%2e%2e/player_web.py'):
        assert request(path)['code'] == 404


def test_every_local_module_import_is_served():
    # Splitting the scene must not leave a module outside the asset allowlist.
    import re

    from whisperwick.web3d_assets import ASSETS, asset

    for name in ASSETS:
        if not name.endswith('.js'):
            continue
        source = asset(name)[0].decode()
        for dependency in re.findall(r"['\"]\./([^'\"]+\.js)['\"]", source):
            response = request('/web3d/' + dependency)
            assert response['code'] == 200, (name, dependency)
            assert response['headers']['Content-Type'].startswith('text/javascript')
