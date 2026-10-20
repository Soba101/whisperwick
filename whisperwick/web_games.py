"""One game per named player (per browser in local play), with its own world and game thread.

The manager only starts and stops games. It never looks inside a world.
"""

import hashlib
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from whisperwick.player_web import WebPlayer

IDLE_SECONDS = 30 * 60  # a game nobody has asked about for this long is stopped
MAX_GAMES = 5


@dataclass
class Game:
    token: str
    player: WebPlayer
    thread: threading.Thread
    last_seen: float
    name: str = "owner"
    feedback_count: int = 0  # Private submissions never enter the player inbox.


class GameManager:
    def __init__(
        self,
        launch: Callable[..., tuple[WebPlayer, threading.Thread]],
        max_games: int = MAX_GAMES,
        idle_seconds: float = IDLE_SECONDS,
        choose_roles: bool = False,
        default_role: str | None = None,
        choose_crimes: bool = False,
        default_crime: str = "random",
        clock: Callable[[], float] = time.monotonic,  # tests pass their own clock
    ):
        self.choose_roles, self.default_role = choose_roles, default_role
        self.choose_crimes, self.default_crime = choose_crimes, default_crime
        self.launch = launch  # starts a fresh game thread with its own world and db
        self.max_games, self.idle_seconds, self.clock = max_games, idle_seconds, clock
        self.lock = threading.Lock()
        self.games: dict[str, Game] = {}

    def _reap(self) -> None:
        """Stop games that nobody asked about lately, which frees their seats. Lock held."""
        now = self.clock()
        for token in [t for t, g in self.games.items() if now - g.last_seen > self.idle_seconds]:
            self.games.pop(token).player.stop()

    def _seats_used(self) -> int:
        """A finished game costs no model time, so it does not hold a seat. Lock held."""
        return sum(1 for g in self.games.values() if not g.player.finished)

    def _create(
        self, role: str | None = None, crime: str | None = None, name: str | None = None
    ) -> Game | None:
        if self._seats_used() >= self.max_games:
            return None
        # Names travel outside the world. Local anonymous browsers still get separate games.
        kwargs = {"player_name": name} if name is not None else {}
        if self.choose_crimes:
            player, thread = self.launch(
                role, self.default_crime if crime is None else str(crime), **kwargs)
        else:
            player, thread = (self.launch(role, **kwargs) if self.choose_roles
                              else self.launch(**kwargs))
        player.name = name or "owner"
        game = Game(secrets.token_urlsafe(16), player, thread, self.clock(), name=name or "owner")
        self.games[game.token] = game
        return game

    def get(self, token: str | None, name: str | None = None) -> Game | None:
        """The caller's running game, or None. Counts as a visit."""
        with self.lock:
            self._reap()
            game = self.games.get(token or "")
            if game and (name is None or game.name == name):
                game.last_seen = self.clock()
            return game if game and (name is None or game.name == name) else None

    def open(self, token: str | None, name: str | None = None) -> Game | None:
        """The caller's game, or a new one. None when every seat is taken."""
        with self.lock:
            self._reap()
            game = self.games.get(token or "")
            if game and (name is None or game.name == name):
                game.last_seen = self.clock()
                return game
            self._drop_name(name)
            return self._create(name=name)

    def replace(
        self, token: str | None, role: str | None = None, crime: str | None = None,
        name: str | None = None,
    ) -> Game | None:
        """End the caller's game and start a fresh one (the New game button)."""
        with self.lock:
            self._reap()
            self._discard(token, name)
            self._drop_name(name)
            return self._create(role, crime, name)

    def _discard(self, token: str | None, name: str | None) -> None:
        old = self.games.get(token or "")
        if old and (name is None or old.name == name):
            self.games.pop(old.token).player.stop()

    def _drop_name(self, name: str | None) -> None:
        # A second browser replaces the named player's old game, even at capacity.
        if name is not None:
            for token in [t for t, g in self.games.items() if g.name == name]:
                self.games.pop(token).player.stop()

    def seat_label(self, token: str | None, name: str | None = None) -> str:
        with self.lock:
            self._reap()
            live = [g.token for g in self.games.values() if not g.player.finished]
            game = self.games.get(token or "")
            if token in live and (name is None or game.name == name):
                seat = live.index(token) + 1
            else:
                seat = min(len(live) + 1, self.max_games)
            return f"Seat {seat} of {self.max_games}"

    def discard(self, token: str | None, name: str | None = None) -> None:
        """Leave the old game before choosing another role."""
        with self.lock:
            self._discard(token, name)

    def active(self) -> list[dict]:
        """Owner summary from cached pictures. Viewing it never renews idle seats."""
        with self.lock:
            self._reap()
            result = []
            for game in self.games.values():
                with game.player.cv:
                    if game.player.finished:
                        continue
                    sc = game.player.sc
                    result.append({"id": hashlib.sha256(game.token.encode()).hexdigest(),
                                   "name": game.name, "role": sc.role_id,
                                   "crime": sc.crime_seed,
                                   "clock": game.player.view.get("clock", "")})
            return result

    def stop(self, game_id: str) -> None:
        """Resolve the public ID without exposing another browser's game cookie."""
        with self.lock:
            token = next((t for t in self.games
                          if hashlib.sha256(t.encode()).hexdigest() == game_id), None)
            if token is None:
                raise ValueError("Game has already stopped.")
            # Use the same stop path as leaving a game or replacing a browser.
            self._discard(token, None)

    def close_all(self) -> list[threading.Thread]:
        """Stop every game (server closing). Returns the threads so a test can join them."""
        with self.lock:
            games, self.games = list(self.games.values()), {}
        for g in games:
            g.player.stop()
        return [g.thread for g in games]
