"""Authentication helpers kept apart from game routes."""

from whisperwick import web_auth
from whisperwick.invite_players import Players
from whisperwick.invite_requests import Requests


class Access:
    players: Players | None = None
    requests: Requests | None = None
    player_name: str | None = None

    def owner_cookie_ok(self) -> bool:
        # Local play without a key does not imply permission to manage invitations.
        return bool(self.key and web_auth.key_ok(
            self.key, self.cookies().get(web_auth.KEY_COOKIE)))

    def identity(self, supplied: str | None) -> str | None:
        if self.key and web_auth.key_ok(self.key, supplied):
            return "owner"
        return self.players.authenticate(supplied) if self.players else None

    def key_cookie_ok(self) -> bool:
        self.player_name = self.identity(self.cookies().get(web_auth.KEY_COOKIE))
        if self.player_name and self.player_name != "owner" and self.players:
            self.players.visit(self.player_name)
        # No owner key still means local play, with separate anonymous browsers.
        return not self.key or self.player_name is not None

    def game_started(self, game) -> None:
        if self.player_name and self.player_name != "owner" and self.players:
            self.players.visit(self.player_name, new_game=True)
