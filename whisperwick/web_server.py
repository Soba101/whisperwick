"""A tiny local web server for the play page. Standard library only.

It binds to 127.0.0.1, so only this computer can reach it. It never touches the world:
GET /state reads the player's cached picture, and the POSTs only queue a request that
the engine then judges like any other. The page is never trusted to decide anything.
"""

import json
import socketserver
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from whisperwick.player_web import WAIT_CHOICES, WebPlayer, intent_from
from whisperwick.web_page import render_page

MAX_BODY = 20_000  # bytes; a message is at most a few hundred characters


class Handler(BaseHTTPRequestHandler):
    player: WebPlayer  # set on the subclass made by make_server

    def log_message(self, *args) -> None:
        pass  # keep the terminal quiet: it shows the game's own progress

    def send(self, code: int, body: bytes, kind: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, code: int, data: dict) -> None:
        self.send(code, json.dumps(data).encode(), "application/json")

    def host_ok(self) -> bool:
        """Only our own address as Host. Stops another website from using this server."""
        port = self.server.server_address[1]
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def do_GET(self) -> None:
        if not self.host_ok():
            return self.send_json(403, {"error": "bad host"})
        url = urlparse(self.path)
        if url.path == "/":
            return self.send(200, render_page().encode(), "text/html; charset=utf-8")
        if url.path == "/state":
            try:
                since = max(0, int(parse_qs(url.query).get("since", ["0"])[0]))
            except ValueError:
                since = 0
            return self.send_json(200, self.player.snapshot(since))
        self.send_json(404, {"error": "not found"})

    def read_body(self) -> dict | None:
        """The JSON body. JSON content type is required, so a plain cross-site form cannot post."""
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return None
        try:
            size = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(size)) if 0 < size <= MAX_BODY else {}
        except ValueError:
            return None
        return body if isinstance(body, dict) else None

    def do_POST(self) -> None:
        if not self.host_ok():
            return self.send_json(403, {"error": "bad host"})
        body = self.read_body()
        if body is None:
            return self.send_json(400, {"error": "bad request"})
        path = urlparse(self.path).path
        if path == "/act":
            intent = intent_from(body)
            if intent is None:
                return self.send_json(400, {"error": "that action is not available"})
            sent = self.player.submit("act", intent)
        elif path == "/wait" and body.get("minutes") in WAIT_CHOICES:
            sent = self.player.submit("wait", body["minutes"])
        elif path == "/quit":
            sent = self.player.submit("quit", None)
        else:
            return self.send_json(404, {"error": "not found"})
        if not sent:
            return self.send_json(409, {"error": "it is not your turn"})
        self.send_json(200, {"ok": True})


class LocalServer(ThreadingHTTPServer):
    """ThreadingHTTPServer without the reverse-DNS lookup of its own address.

    The standard server_bind calls socket.getfqdn("127.0.0.1"), which took 35 s on this Mac
    before the page could start. We only ever serve 127.0.0.1, so the name is known.
    """

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name, self.server_port = host, port


def make_server(player: WebPlayer, port: int) -> ThreadingHTTPServer:
    """A server on 127.0.0.1 only. Port 0 picks a free port (tests use that)."""
    handler = type("PlayHandler", (Handler,), {"player": player})
    server = LocalServer(("127.0.0.1", port), handler)
    server.daemon_threads = True  # open page polls must not keep the process alive
    return server
