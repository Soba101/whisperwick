"""A tiny web server for the play page. Standard library only.

It binds to 127.0.0.1, so only this computer can reach it directly (a tunnel may forward
a public name to it, see web_auth for the key and Host rules). It never touches the world:
GET /state reads the caller's cached picture, and the POSTs only queue a request that
the engine then judges like any other. The page is never trusted to decide anything.
Each named player has one game; anonymous local browsers stay separate (see web_games).
"""

import json
import socketserver
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from whisperwick import feedback, web_auth
from whisperwick.crime.selection import crime_number
from whisperwick.invite_files import atomic_write, locked
from whisperwick.invite_players import Players
from whisperwick.invite_requests import Requests
from whisperwick.player_web import WAIT_CHOICES, intent_from
from whisperwick.roles import ROLE_IDS
from whisperwick.web_access import Access
from whisperwick.web_admin import AdminRoutes
from whisperwick.web_games import Game, GameManager
from whisperwick.web_get import ReadRoutes
from whisperwick.web_page import plain_page

MAX_BODY = 20_000  # bytes; a message is at most a few hundred characters


class Handler(Access, AdminRoutes, ReadRoutes, BaseHTTPRequestHandler):
    games: GameManager  # set on the subclass made by make_server
    key: str | None
    hosts: set[str]

    def log_message(self, *args) -> None:
        pass  # keep the terminal quiet: it shows the game's own progress

    def send(self, code: int, body: bytes, kind: str, cookies: list[str] | None = None) -> None:
        self.send_response(code)
        for c in cookies or []:
            self.send_header("Set-Cookie", c)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, code: int, data: dict, cookies: list[str] | None = None) -> None:
        self.send(code, json.dumps(data).encode(), "application/json", cookies)

    def send_text(self, code: int, text: str, cookies: list[str] | None = None) -> None:
        self.send(code, plain_page(text).encode(), "text/html; charset=utf-8", cookies)

    def host_ok(self) -> bool:
        """Only our local port or an allowed name on any port. Stops other sites using this."""
        return web_auth.host_allowed(self.headers.get("Host"), self.hosts)

    def secure(self) -> bool:
        """Cookies are Secure when the page came in through a public (HTTPS) name."""
        return not web_auth.is_local(self.headers.get("Host"))

    def cookies(self) -> dict[str, str]:
        return web_auth.parse_cookies(self.headers.get("Cookie"))

    def game_cookie(self, game: Game) -> list[str]:
        return [web_auth.cookie_header(web_auth.GAME_COOKIE, game.token, self.secure())]

    def read_body(self) -> dict | None:
        """The JSON body. JSON content type is required, so a plain cross-site form cannot post."""
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return None
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                return None
            body = json.loads(self.rfile.read(size))
        except ValueError:
            return None
        return body if isinstance(body, dict) else None

    def do_POST(self) -> None:
        if not self.host_ok():
            return self.send_json(403, {"error": "bad host"})
        path = urlparse(self.path).path
        if path.startswith("/admin"):
            return self.admin_post(path)  # owner check comes first inside
        if path == "/request":
            if not self.requests.allow():
                return self.send(429, b"Too many requests. Please try again later.", "text/plain")
            body = self.read_body()
            code, message = (400, "bad request") if body is None else self.requests.save(body)
            return self.send(code, message.encode(), "text/plain; charset=utf-8")
        if not self.key_cookie_ok():
            return self.send_json(403, {"error": "key needed"})
        body = self.read_body()
        if body is None:
            return self.send_json(400, {"error": "bad request"})
        token = self.cookies().get(web_auth.GAME_COOKIE)
        if path == "/choose":
            self.games.discard(token, self.player_name)
            return self.send_json(200, {"ok": True})
        if path == "/newgame":
            role = body.get("role") or None
            if role is not None and role not in ROLE_IDS:
                return self.send_json(400, {"error": "unknown role"})
            crime = body.get("crime")
            if self.games.choose_crimes:
                try:
                    # Validate before replacing a running game. Draw entropy only at launch.
                    if crime is not None and crime != "random":
                        crime_number(crime)
                except ValueError as e:
                    return self.send_json(400, {"error": str(e)})
            game = self.games.replace(token, role, crime, self.player_name)
            if game is None:
                return self.send_json(503, {"error": "All seats are taken, try again later."})
            self.game_started(game)
            return self.send_json(200, {"ok": True}, self.game_cookie(game))
        game = self.games.get(token, self.player_name)
        if game is None:
            return self.send_json(409, {"error": "no game here, reload the page"})
        if path == "/feedback":
            code, result = feedback.save(game, body)
            return self.send_json(code, result)
        player = game.player
        if path == "/accuse":
            with player.cv:
                sent = player.ending.choose(body.get("target"))
        elif path == "/act":
            intent = intent_from(body)
            if intent is None:
                return self.send_json(400, {"error": "that action is not available"})
            sent = player.submit("act", intent)
        elif path == "/wait" and body.get("minutes") in WAIT_CHOICES:
            sent = player.submit("wait", body["minutes"])
        elif path == "/quit":
            sent = player.submit("quit", None)
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

    # The 3D page asks for many models and textures at once. The default queue of 5
    # waiting connections overflowed and reset requests, so some scripts never loaded.
    request_queue_size = 128

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name, self.server_port = host, port


def make_server(
    games: GameManager, port: int, key: str | None = None, allow_hosts: tuple[str, ...] = (),
    players: Players | None = None, requests: Requests | None = None,
    admin_key: str | None = None,
) -> ThreadingHTTPServer:
    """A server on 127.0.0.1 only. Port 0 picks a free port (tests use that)."""
    players = players or Players(feedback.DEFAULT_PATH.parent)
    requests = requests or Requests(players.folder)
    if allow_hosts:
        with locked(players.folder):
            atomic_write(players.folder / "invite-host.json", json.dumps(allow_hosts[0]))
    server = LocalServer(("127.0.0.1", port), Handler)
    # The real port is only known after binding (port 0), and the Host rule needs it.
    real_port = server.server_address[1]
    hosts = web_auth.allowed_hosts(real_port, allow_hosts)
    handler = type("PlayHandler", (Handler,), {"games": games, "key": key or None, "hosts": hosts,
                                             "players": players, "requests": requests,
                                             "admin_key": admin_key or None})
    server.RequestHandlerClass = handler
    server.daemon_threads = True  # open page polls must not keep the process alive
    return server
