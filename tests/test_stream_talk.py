"""Incomplete JSON is display only. No parser shortcut may become a world action."""

import json

import pytest
from helpers import fresh_world
from web_helpers import SC

from whisperwick import llm_agent, settings
from whisperwick.llm_client import FakeClient, LLMError
from whisperwick.player_web import WebPlayer
from whisperwick.stream_talk import partial_message


@pytest.mark.parametrize(('text', 'message'), [
    ('', None), ('{', None), ('{"action":"talk', None),
    ('{"action":"talk","message":"Hello', 'Hello'),
    ('{"message":"First","action":"talk"', 'First'),
    ('{"action":"look","message":"Hidden', None),
    ('{"nested":{"action":"talk","message":"Hidden"}', None),
    ('{"action":"talk","message":null', None),
    ('{"action":"talk","message":"a\\', 'a'),
    ('{"action":"talk","message":"a\\u00', 'a'),
    ('{"action":"talk","message":"a\\uD83D', 'a'),
    ('{"action":"talk","message":"a\\uD83D\\uDE00', 'a😀'),
    ('{"action":"talk","message":"a\\n\\"b', 'a\n"b'),
    ('{"message":"action: talk, message: fake"}', None),
    ('{"action":"talk","message":"bad\\x', None),
])
def test_partial_message(text, message):
    assert partial_message(text) == message


def test_every_prefix_handles_escapes_and_key_order():
    value = {'message': 'A "quote", a slash \\, and 😀. Done.', 'action': 'talk'}
    raw = json.dumps(value)
    for end in range(len(raw) + 1):
        preview = partial_message(raw[:end])
        assert preview is None or value['message'].startswith(preview)
    assert partial_message(raw) == value['message']


def test_live_visibility_cleanup_and_commit_identity():
    world, player = fresh_world(), WebPlayer(SC)
    player.on_turn(world, 'npc_bob')
    player.on_live_talk(world, 'npc_alice', 'Hidden')  # Alice is at the inn.
    assert player.snapshot()['live_talk'] == {}
    player.on_live_talk(world, 'npc_bob', 'Hello.')
    live = player.snapshot()['live_talk']['npc_bob']
    assert live['name'] == 'Bob' and live['message'] == 'Hello.'
    assert not any('Hello.' in line for line in player.feed)
    player.on_live_talk(world, 'npc_bob', None)
    assert player.snapshot()['live_talk'] == {}
    intent = llm_agent.decide(world, 'npc_bob', FakeClient([
        {'action': 'talk', 'target': 'player', 'message': 'Hello.'}]))
    result = world.act(intent)
    player.on_event(world, result.event)
    assert player.snapshot()['speech_stream']['npc_bob'] == live['sequence']
    assert 'Hello.' in player.snapshot()['speech']['npc_bob']


@pytest.mark.parametrize('reply', [
    {'action': 'look', 'message': None},
    {'action': 'talk', 'target': 'npc_alice', 'message': 'Rejected.'},
    {'action': 'talk', 'message': 123},
    None,
])
def test_bad_non_talk_and_rejected_calls_leave_no_live_line(reply):
    world, player = fresh_world(), WebPlayer(SC)
    player.on_turn(world, 'npc_bob')

    class Client:
        live_talk = player.on_live_talk

        def chat(self, messages, schema, on_text):
            on_text('{"action":"talk","message":"Preview.')
            assert player.snapshot()['live_talk']
            if reply is None:
                raise LLMError('broken stream')
            return reply

    llm_agent.act(world, 'npc_bob', Client())
    assert player.snapshot()['live_talk'] == {}
    assert not any('Preview.' in line or 'Rejected.' in line for line in player.feed)


def test_stream_setting_is_web_only(monkeypatch, tmp_path):
    env = tmp_path / '.env'
    monkeypatch.delenv('WHISPERWICK_STREAM_TALK', raising=False)
    assert settings.stream_talk(True, env)
    assert not settings.stream_talk(False, env)
    env.write_text('WHISPERWICK_STREAM_TALK=off\n')
    assert not settings.stream_talk(True, env)
    monkeypatch.setenv('WHISPERWICK_STREAM_TALK', 'on')
    assert settings.stream_talk(True, env)
    assert not settings.stream_talk(False, env)
    monkeypatch.setenv('WHISPERWICK_STREAM_TALK', 'bad')
    with pytest.raises(ValueError, match='WHISPERWICK_STREAM_TALK'):
        settings.stream_talk(True, env)
