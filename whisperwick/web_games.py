"""One game per device. Each browser gets its own player, world, database and game thread.

The manager only starts and stops games. It never looks inside a world.
"""

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from whisperwick.player_web import WebPlayer

IDLE_SECONDS = 30 * 60  # a game nobody has asked about for this long is stopped
MAX_GAMES = 3


@dataclass
class Game:
    token: str
    player: WebPlayer
    thread: threading.Thread
    last_seen: float


class GameManager:
    def __init__(
        self,
        launch: Callable[[], tuple[WebPlayer, threading.Thread]],
        max_games: int = MAX_GAMES,
        idle_seconds: float = IDLE_SECONDS,
        clock: Callable[[], float] = time.monotonic,  # tests pass their own clock
    ):
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

    def _create(self) -> Game | None:
        if self._seats_used() >= self.max_games:
            return None
        player, thread = self.launch()
        game = Game(secrets.token_urlsafe(16), player, thread, self.clock())
        self.games[game.token] = game
        return game

    def get(self, token: str | None) -> Game | None:
        """The caller's running game, or None. Counts as a visit."""
        with self.lock:
            self._reap()
            game = self.games.get(token or "")
            if game:
                game.last_seen = self.clock()
            return game

    def open(self, token: str | None) -> Game | None:
        """The caller's game, or a new one. None when every seat is taken."""
        with self.lock:
            self._reap()
            game = self.games.get(token or "")
            if game:
                game.last_seen = self.clock()
                return game
            return self._create()

    def replace(self, token: str | None) -> Game | None:
        """End the caller's game and start a fresh one (the New game button)."""
        with self.lock:
            self._reap()
            old = self.games.pop(token or "", None)
            if old:
                old.player.stop()
            return self._create()

    def close_all(self) -> list[threading.Thread]:
        """Stop every game (server closing). Returns the threads so a test can join them."""
        with self.lock:
            games, self.games = list(self.games.values()), {}
        for g in games:
            g.player.stop()
        return [g.thread for g in games]
