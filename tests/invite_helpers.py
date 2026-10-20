"""Real invite handlers with in-memory HTTP streams and no sockets or model calls."""

import json
import threading
from io import BytesIO

from web_helpers import SC

from whisperwick import web_auth
from whisperwick.invite_requests import Requests
from whisperwick.player_web import WebPlayer
from whisperwick.web_games import GameManager
from whisperwick.web_server import Handler


def manager(**options):
    def launch(player_name="owner"):
        return WebPlayer(SC), threading.Thread()

    return GameManager(launch, **options)


def request(store, games, path="/", body=None, *, key=None, token=None, waiting=None,
            host="play.example", kind="application/json", raw=None, length=None,
            headers: dict | None = None):
    h = Handler.__new__(Handler)
    h.players, h.requests = store, waiting or Requests(store.folder)
    h.games, h.key, h.path = games, "owner-secret", path
    h.hosts = web_auth.allowed_hosts(8000, ("play.example",))
    cookies = {}
    if key is not None:
        cookies[web_auth.KEY_COOKIE] = key
    if token is not None:
        cookies[web_auth.GAME_COOKIE] = token
    raw = raw if raw is not None else json.dumps(body).encode() if body is not None else None
    h.headers = {"Host": host, "Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
                 "Content-Type": kind, "Content-Length": str(length if length is not None
                                                             else len(raw or b""))}
    h.headers.update(headers or {})
    h.rfile, h.wfile = BytesIO(raw or b""), BytesIO()
    result = {"headers": {}}
    h.send_response = lambda code: result.update(code=code)
    h.send_header = lambda name, value: result["headers"].update({name: value})
    h.end_headers = lambda: None
    h.do_POST() if raw is not None else h.do_GET()
    result["body"] = h.wfile.getvalue()
    return result
