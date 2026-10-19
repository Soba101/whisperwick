"""A local fake llama-server exercises real HTTP, SSE framing and the run loop."""

import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from helpers import fresh_world
from web_helpers import SC

from whisperwick import llm_agent
from whisperwick.llm_client import LlamaServerClient, LLMError
from whisperwick.llm_sim import run_llm
from whisperwick.llm_sse import read_stream
from whisperwick.player_web import WebPlayer

TALK = {'action': 'talk', 'target': 'player', 'item': None,
        'message': 'Hello "friend". Café 😀.', 'accuses': None, 'defends': None}


@pytest.fixture(params=["memory", "http"])
def server(request, monkeypatch):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Test output should contain assertions, not request logs.

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(body)
            properties = body['response_format']['json_schema']['schema']['properties']
            if 'thoughts' in properties:
                reply = {'thoughts': 'all quiet', 'suspect': None, 'sureness': 'unsure',
                         'because': [], 'trust': []}
            elif '(npc_bob)' in body['messages'][0]['content']:
                reply = TALK
            else:
                reply = {'action': 'look', 'target': None, 'message': None}
            text = json.dumps(reply, ensure_ascii=False)
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream' if body['stream']
                             else 'application/json')
            self.end_headers()
            if not body['stream']:
                self.wfile.write(json.dumps({'choices': [{'message': {'content': text}}],
                                            'usage': {'completion_tokens': 9}}).encode())
                return
            self.wfile.write(b': keepalive\r\n\r\n')
            # One character per delta puts boundaries inside JSON keys and escapes.
            for char in text:
                chunk = {'choices': [{'delta': {'content': char}}]}
                self.wfile.write(('data: ' + json.dumps(chunk) + '\r\n\r\n').encode())
                self.wfile.flush()
            self.wfile.write(b'data: {"choices":[],"usage":{"completion_tokens":9}}\n\n')
            self.wfile.write(b'data: [DONE]\n\n')

    if request.param == 'memory':
        def urlopen(req, timeout):
            # The same handler and SSE bytes work without socket permission in CI.
            handler = Handler.__new__(Handler)
            handler.headers = {'Content-Length': str(len(req.data))}
            handler.rfile, handler.wfile = io.BytesIO(req.data), io.BytesIO()
            handler.send_response = lambda *args: None
            handler.send_header = lambda *args: None
            handler.end_headers = lambda: None
            handler.do_POST()
            handler.wfile.seek(0)
            return handler.wfile

        monkeypatch.setattr('urllib.request.urlopen', urlopen)
        yield 'http://fake/v1', calls
        return
    try:
        httpd = HTTPServer(('127.0.0.1', 0), Handler)
    except PermissionError:
        pytest.skip('This sandbox cannot bind localhost sockets; memory transport still runs.')
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{httpd.server_port}/v1', calls
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def test_same_intent_and_request_with_streaming(server):
    url, calls = server
    world, player = fresh_world(), WebPlayer(SC)
    player.on_turn(world, 'npc_bob')
    previews = []
    client = LlamaServerClient(url, 'test', temperature=.63)
    plain = llm_agent.decide(world, 'npc_bob', client, slot=3)

    def live(world, npc, message):
        player.on_live_talk(world, npc, message)
        previews.append(player.snapshot()['live_talk'].copy())

    client.live_talk = live
    streamed = llm_agent.decide(world, 'npc_bob', client, slot=3)
    assert streamed.model_dump_json() == plain.model_dump_json()
    assert streamed.message == TALK['message']
    assert previews[-1] == {} and any(p.get('npc_bob', {}).get('message') for p in previews)
    assert {**calls[0], 'stream': True} == calls[1]
    assert calls[1]['id_slot'] == 3 and calls[1]['cache_prompt']
    assert client.usage.summary()['output_tokens'] == 18


def test_stub_run_event_log_is_identical(server):
    url, calls = server
    plain, streamed = fresh_world(), fresh_world()
    client = LlamaServerClient(url, 'test')
    run_llm(plain, client, 241, agent_memory=False, slots=2)
    player = WebPlayer(SC)
    client.live_talk = player.on_live_talk
    boundary = len(calls)
    run_llm(streamed, client, 241, agent_memory=False, slots=2,
            on_turn=player.on_turn, on_event=player.on_event)
    assert plain.log.all()  # A comparison of empty logs proves nothing.
    assert [e.model_dump_json() for e in plain.log.all()] == [
        e.model_dump_json() for e in streamed.log.all()]
    assert plain.state_hash() == streamed.state_hash()
    assert player.snapshot()['live_talk'] == {}
    thoughts = [c for c in calls[boundary:] if 'thoughts' in
                c['response_format']['json_schema']['schema']['properties']]
    assert thoughts and all(not c['stream'] for c in thoughts)


@pytest.mark.parametrize('wire', [
    b'data: {"choices":[{"delta":{"content":"{}"}}]}\n\n',
    b'data: invalid\n\ndata: [DONE]\n\n',
    b'data: {"error":"server failed"}\n\ndata: [DONE]\n\n',
])
def test_broken_stream_never_returns_an_intent(wire, monkeypatch):
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: io.BytesIO(wire))
    client = LlamaServerClient('http://fake/v1', 'test')
    with pytest.raises(LLMError):
        client.chat([], {}, on_text=lambda text: None)
    assert client.usage.summary()['errors'] == 1


def test_sse_multiline_events_and_usage():
    seen = []
    wire = (b': hello\n\ndata: {"choices":\ndata: [{"delta":{"content":"{}"}}]}\n\n'
            b'data: {"choices":[],"usage":{"completion_tokens":2}}\n\n'
            b'data: [DONE]\n\n')
    reply = read_stream(io.BytesIO(wire), seen.append)
    assert seen == ['{}']
    assert reply['usage']['completion_tokens'] == 2
