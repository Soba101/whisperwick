"""Read routes. They only use cached player pictures, never a world database."""

import hashlib
from html import escape
from urllib.parse import parse_qs, urlparse

from whisperwick import web3d_assets, web_auth
from whisperwick.web_page import render_page
from whisperwick.web_request_page import REQUEST_PAGE


class ReadRoutes:
    def welcome(self, token) -> str:
        seat = self.games.seat_label(token, self.player_name)
        link = ' · <a href="/admin">Admin</a>' if self.owner_cookie_ok() else ""
        return f"<span>Welcome, {escape(self.player_name or 'owner')} · {seat}{link}</span>"

    def start_page(self, token) -> str:
        seat = self.games.seat_label(token, self.player_name)
        return render_page(self.player_name or "owner", seat, admin=self.owner_cookie_ok())

    def do_GET(self) -> None:
        if not self.host_ok():
            return self.send_json(403, {"error": "bad host"})
        url = urlparse(self.path)
        if url.path == "/admin" or url.path.startswith("/admin/"):
            return self.admin_get(url.path)  # non-owners get a plain 404 there
        query = parse_qs(url.query)
        supplied = query.get("key", [""])[0]
        if url.path in ("/", "/3d") and supplied and self.identity(supplied):
            # The link with the key sets the cookie, then drops the key from the address bar.
            cookie = web_auth.cookie_header(web_auth.KEY_COOKIE, supplied, self.secure())
            self.send_response(302)
            self.send_header("Location", url.path)
            self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            return self.end_headers()
        if not self.key_cookie_ok():
            if url.path in ("/", "/3d"):
                return self.send(403, REQUEST_PAGE.encode(), "text/html; charset=utf-8")
            return self.send_json(403, {"error": "key needed"})
        token = self.cookies().get(web_auth.GAME_COOKIE)
        if url.path == "/3d" and query.get("fixture") == ["1"]:
            return self.send(200, *web3d_assets.asset("index.html"))
        if url.path in ("/", "/3d"):
            # Roles are picked on the 2D page (week 13); after picking, /3d reloads into 3D.
            if self.games.choose_roles and self.games.get(token, self.player_name) is None:
                return self.send(200, self.start_page(token).encode(), "text/html; charset=utf-8")
            previous = self.games.get(token, self.player_name)
            # a new browser starts its own game here
            game = self.games.open(token, self.player_name)
            if game is None:
                return self.send_text(503, "All seats are taken, try again later.")
            if previous is None:
                self.game_started(game)
            cookies = self.game_cookie(game) if game.token != token else None
            body = (web3d_assets.asset("index.html")[0] if url.path == "/3d"
                    else self.start_page(game.token).encode())
            if url.path == "/3d":
                welcome = self.welcome(game.token)
                body = body.replace(b"<strong>Whisperwick</strong>",
                                    ("<strong>Whisperwick</strong>" + welcome).encode())
            return self.send(200, body, "text/html; charset=utf-8", cookies)
        if url.path.startswith("/web3d/"):
            found = web3d_assets.asset(url.path.removeprefix("/web3d/"))
            if found:
                return self.send(200, *found)
        if url.path == "/state":
            game = self.games.get(token, self.player_name)
            if game is None and self.games.choose_roles:
                choice = {"select_role": True, "default_role": self.games.default_role}
                if self.games.choose_crimes:
                    choice["default_crime"] = self.games.default_crime
                return self.send_json(200, choice)
            if game is None:
                return self.send_json(200, {"gone": True})  # the page then reloads itself
            try:
                since = max(0, int(query.get("since", ["0"])[0]))
            except ValueError:
                since = 0
            state = game.player.snapshot(since)
            # Notes need a game key without making the HttpOnly cookie readable.
            state["game_id"] = hashlib.sha256(game.token.encode()).hexdigest()
            return self.send_json(200, state)
        self.send_json(404, {"error": "not found"})

