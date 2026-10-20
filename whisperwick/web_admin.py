"""Owner routes. They manage access and seats, never world state."""

import hmac
import secrets

from whisperwick import feedback
from whisperwick.invite_actions import invite_link
from whisperwick.invite_files import locked, rows, valid_name
from whisperwick.web_admin_page import render_admin

# One random token lives only in this process. A restart invalidates open admin forms.
CSRF_TOKEN = secrets.token_urlsafe(32)
CSRF_HEADER = "X-CSRF-Token"
ACTIONS = {"/admin/approve", "/admin/decline", "/admin/invite", "/admin/revoke", "/admin/stop"}


class AdminRoutes:
    csrf_token = CSRF_TOKEN

    def admin_get(self, path: str) -> None:
        if not self.owner_cookie_ok() or path != "/admin":
            return self.send_json(404, {"error": "not found"})
        try:
            with locked(self.players.folder):
                # Hashes are authentication data, not page data.
                players = [{k: v for k, v in p.items() if k != "key_hash"}
                           for p in self.players.read()]
                requests = rows(self.requests.path)
            entries = feedback.recent(self.players.folder / "feedback.jsonl")
            page = render_admin(self.csrf_token, self.games.active(), self.games.max_games,
                                requests, players, entries)
        except (OSError, ValueError):
            return self.send_json(500, {"error": "Could not read admin data. Please try again."})
        return self.send(200, page.encode(), "text/html; charset=utf-8")

    def admin_post(self, path: str) -> None:
        # Check this before parsing the body or CSRF header. Other keys see only a 404.
        if not self.owner_cookie_ok() or path not in ACTIONS:
            return self.send_json(404, {"error": "not found"})
        supplied = self.headers.get(CSRF_HEADER, "")
        if not hmac.compare_digest(supplied.encode(), self.csrf_token.encode()):
            return self.send_json(403, {"error": "Reload the admin page and try again."})
        body = self.read_body()
        field = "id" if path == "/admin/stop" else "name"
        if body is None or set(body) != {field} or not isinstance(body[field], str):
            return self.send_json(400, {"error": "bad request"})
        try:
            result = {"ok": True}
            if path == "/admin/stop":
                self.games.stop(body["id"])
            else:
                name = valid_name(body["name"])
                if path in ("/admin/approve", "/admin/invite"):
                    # The Host allowlist was checked before this route. Local links use HTTP.
                    result["link"] = invite_link(self.players, name, path == "/admin/approve",
                                                 self.headers.get("Host"), self.secure())
                elif path == "/admin/decline":
                    self.requests.decline(name)
                else:
                    stored = self.players.revoke(name)
                    # A revoked key is refused on the next request, but its game would
                    # keep a seat until it idles out.
                    self.games.stop_player(stored)
        except ValueError as e:
            return self.send_json(400, {"error": str(e)})
        except OSError:
            return self.send_json(500, {"error": "Could not save change. Please try again."})
        # No secret is retained on the handler, in a URL or in a log.
        return self.send_json(200, result)
