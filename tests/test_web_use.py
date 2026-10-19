"""Both web pages share use choices, witnessed gestures and conversation focus."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from helpers import SCENARIO

from whisperwick import web_state
from whisperwick.player_web import WebPlayer, intent_from
from whisperwick.scenario import build_world, load_scenario
from whisperwick.web_js import JS

SC = load_scenario(SCENARIO.with_name("murder_of_the_mayor_goods.yaml"))


def snapshot(world, player):
    with player.cv:
        player._refresh(world)
    return player.snapshot()


def test_use_choices_reasons_and_authorization():
    world, player = build_world(SC), WebPlayer(SC)

    def choice():
        return next(a for a in snapshot(world, player)['actions'] if a['action'] == 'use')

    assert choice()['reason'] == 'that cannot be used up'  # Wren has only coins.
    for key in world.items_held('player'):
        world.items[key].holder = 'npc_bob'
    assert choice()['reason'] == 'you are not holding that'
    world.move('player', 'loc_inn')
    assert world.act(dict(actor='npc_alice', action='give', item='item_tea', target='player')).ok
    a = choice()
    assert a['reason'] is None and a['label'] == 'Use' and a['icon']
    assert a['targets'] is None and not a['message']
    assert a['items'] == [{'id': 'item_tea', 'name': 'cup of tea', 'consumable': True}]
    intent = intent_from({'action': 'use', 'item': 'item_tea'})
    assert intent.actor == 'player' and world.act(intent).ok
    assert choice()['reason'] == 'you are not holding that'
    assert len(web_state.actions_for(web_state.you_view(world))) == 8


def test_use_gesture_is_only_a_witnessed_successful_fact():
    world, player = build_world(SC), WebPlayer(SC)
    snapshot(world, player)
    assert world.act(dict(actor='npc_alice', action='use', item='item_tea')).ok
    assert snapshot(world, player)['interactions'] == []  # Wren is at the Market.
    assert not world.act(dict(actor='npc_victor', action='use', item='item_boots')).ok
    assert snapshot(world, player)['interactions'] == []
    assert world.act(dict(actor='npc_victor', action='use', item='item_apples')).ok
    s = snapshot(world, player)
    # The starting scene occupies the first feed position.
    assert s['interactions'] == [{'id': 'npc_victor', 'sequence': 2}]
    assert 'Victor eats the basket of apples' in s['feed'][-1]
    assert snapshot(world, player)['interactions'] == s['interactions']
    # The existing gesture path plays this clip for every accepted interaction.
    figures = Path('whisperwick/web3d/figures.js').read_text()
    assert "r.interactUntil>now ? 'interact-right'" in figures


def test_reply_focus_uses_only_direct_visible_speech_and_resets_on_move():
    world, player = build_world(SC), WebPlayer(SC)
    assert snapshot(world, player)['reply_to'] is None
    def talk(actor, target):
        assert world.act(dict(actor=actor, action='talk', target=target, message='Hello')).ok
        return snapshot(world, player)['reply_to']
    first = talk('npc_bob', 'player')
    assert first['id'] == 'npc_bob'
    assert talk('npc_victor', 'npc_bob') == first  # Overheard talk does not steal focus.
    assert talk('player', 'npc_victor') == first
    latest = talk('npc_victor', 'player')
    assert latest['id'] == 'npc_victor' and latest['sequence'] > first['sequence']
    world.move('player', 'loc_inn')
    assert snapshot(world, player)['reply_to'] is None
    world.move('player', 'loc_market')
    assert snapshot(world, player)['reply_to'] is None


@pytest.mark.parametrize('view', ['2d', '3d'])
def test_browser_controls_follow_speech_clicks_and_room_changes(view):
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is required for browser control checks')
    root = Path('whisperwick/web3d')
    controls = (root / 'controls.js').read_text().replace(
        "import {WhoPicker} from './who.js';", '').replace('export class', 'class')
    source = JS if view == '2d' else (
        (root / 'who.js').read_text().replace('export class', 'class') + controls)
    fixture = json.loads((root / 'fixture_state.json').read_text())
    harness = Path('tests/fixtures/use_controls.cjs').read_text()
    setup, checks = harness.split('// INSERT CONTROLS HERE')
    script = setup + source + '\nconst view = ' + json.dumps(view) + ';\n'
    script += 'const state = ' + json.dumps(fixture) + ';\n' + checks
    result = subprocess.run([node, '-e', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
