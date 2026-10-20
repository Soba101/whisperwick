"""Read routes. They only use cached player pictures, never a world database."""

import hashlib
from html import escape
from urllib.parse import parse_qs, urlparse

from whisperwick import web3d_assets, web_auth
from whisperwick.web_page import render_page
from whisperwick.web_request_page import request_page


class ReadRoutes:
    def welcome(self, token) -> str:
        seat = self.games.seat_label(token, self.player_name)
        # No Admin link on game pages: admin has its own link and key (2026-10-21).
        return f"<span>Welcome, {escape(self.player_name or 'owner')} · {seat}</span>"

    def start_page(self, token) -> str:
        seat = self.games.seat_label(token, self.player_name)
        return render_page(self.player_name or "owner", seat)

    def redirect(self, where: str, cookie: str | None = None) -> None:
        self.send_response(302)
        self.send_header("Location", where)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def come_back(self, path: str) -> None:
        """No key: an approved request ticket signs in; otherwise say where the request is."""
        ticket = self.cookies().get(web_auth.TICKET_COOKIE)
        key = self.players.claim(ticket) if self.players and ticket else None
        if key:
            # Approved: swap the ticket for the player's key, then load the page as usual.
            done = web_auth.cookie_header(web_auth.TICKET_COOKIE, "", self.secure())
            self.send_response(302)
            self.send_header("Location", path)
            self.send_header("Set-Cookie", web_auth.cookie_header(web_auth.KEY_COOKIE, key,
                                                                  self.secure()))
            self.send_header("Set-Cookie", done + "; Max-Age=0")
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            return self.end_headers()
        if not ticket:
            status = ""
        elif self.requests.waiting(ticket):
            status = "waiting"
        else:
            status = "closed"
        return self.send(403, request_page(status).encode(), "text/html; charset=utf-8")

    def do_GET(self) -> None:
        if not self.host_ok():
            return self.send_json(403, {"error": "bad host"})
        url = urlparse(self.path)
        query = parse_qs(url.query)
        admin_try = query.get("key", [""])[0]
        if url.path == "/admin" and self.admin_key and web_auth.key_ok(self.admin_key, admin_try):
            # Same as the play link: set the cookie, then drop the key from the address bar.
            cookie = web_auth.cookie_header(web_auth.ADMIN_COOKIE, admin_try, self.secure())
            return self.redirect("/admin", cookie)
        if url.path == "/admin" or url.path.startswith("/admin/"):
            return self.admin_get(url.path)  # non-owners get a plain 404 there
        supplied = query.get("key", [""])[0]
        if url.path in ("/", "/3d") and supplied and self.identity(supplied):
            # The link with the key sets the cookie, then drops the key from the address bar.
            cookie = web_auth.cookie_header(web_auth.KEY_COOKIE, supplied, self.secure())
            return self.redirect(url.path, cookie)
        if not self.key_cookie_ok():
            if url.path in ("/", "/3d"):
                return self.come_back(url.path)
            return self.send_json(403, {"error": "key needed"})
        token = self.cookies().get(web_auth.GAME_COOKIE)
        if url.path == "/3d" and query.get("fixture") == ["1"]:
            return self.send(200, *web3d_assets.asset("index.html"))
        if url.path in ("/", "/3d"):
            # Roles are picked on the 2D page (week 13); after picking, /3d reloads into 3D.
            if self.games.choose_roles and self.games.get(token, self.player_name) is None:
                return self.send(200, self.start_page(token).encode(), "text/html; charset=utf-8")
            previous = self.games.get(token, self.player_name)
            # 3D is the main view (2026-10-21); the 2D page stays one click away (?view=2d).
            if url.path == "/" and previous is not None and query.get("view") != ["2d"]:
                return self.redirect("/3d")
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

