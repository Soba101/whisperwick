"""The web player: the page sends one action or a wait, the run loop picks it up.

The run loop runs in its own thread and owns the world (its database connection is
bound to that thread). So the world is read ONLY from that thread, inside turn() and
finish(), and the result is kept as plain data. The server threads only read that data
under the lock. That way the page can never see more than Wren could see.
"""

import threading
from collections import deque

from whisperwick import player_terminal, web_state
from whisperwick.actions import ActionResult, Intent
from whisperwick.player import PLAYER_ID, PlayerSource
from whisperwick.scenario import Scenario
from whisperwick.world import World

# Actions the page may send. Arrest and release are for the authority, not for Wren.
ALLOWED = ("move", "look", "talk", "take", "drop", "give", "show")
WAIT_CHOICES = (10, 60)  # minutes
POLL_SECONDS = 0.2  # how often turn() looks up, so quit and stop are noticed


class WebPlayer(PlayerSource):
    def __init__(self, sc: Scenario):
        self.sc = sc
        self.cv = threading.Condition()  # guards everything below
        self.inbox: deque = deque()  # ("act", Intent), ("wait", minutes) or ("quit", None)
        self.awaiting = False  # True only while turn() is blocked, waiting for Wren
        self.stopped = False
        self.finished = False
        self.wait_left = 0  # quiet minutes still to pass before the next prompt
        self.rejection: str | None = None  # the engine's reason for the last refused action
        self.feed: list[str] = []
        self.seen = 0  # how many log events were already looked at for the feed
        self.view: dict = {}
        self.actions: list[dict] = []
        self.world: World | None = None
        self.outcome: str | None = None
        self.secret: str | None = None
        self.error: str | None = None
        self.places = web_state.map_data(sc)  # the map never changes

    # ---- called from the server threads ----

    def submit(self, kind: str, data) -> bool:
        """Queue one thing for Wren. False if it is not Wren's turn, so a late click is ignored."""
        with self.cv:
            if not self.awaiting or self.finished or self.stopped:
                return False
            self.inbox.append((kind, data))
            self.awaiting = False  # the page shows "villagers are acting" at once
            self.rejection = None
            self.cv.notify_all()
            return True

    def stop(self) -> None:
        """Ends the game from outside (server closed). turn() then answers None."""
        with self.cv:
            self.stopped = True
            self.cv.notify_all()

    def snapshot(self, since: int = 0) -> dict:
        """Plain data for GET /state. Feed lines from index `since` on."""
        with self.cv:
            world = self.world
            return {
                "clock": world.clock.label() if world else "",
                "you": self.view,
                "actions": self.actions,
                "places": self.places,
                "awaiting": self.awaiting and not self.finished,
                "finished": self.finished,
                "rejection": self.rejection,
                "feed": self.feed[since:],
                "feed_total": len(self.feed),
                "outcome": self.outcome,
                "secret": self.secret,
                "error": self.error,
            }

    # ---- called from the run loop thread ----

    def _refresh(self, world: World) -> None:
        """Take a new picture of what Wren sees. Lock held by the caller."""
        self.world = world
        events = world.log.all()
        fresh, self.seen = events[self.seen :], len(events)
        self.feed += player_terminal.player_lines(world, fresh)
        self.view = web_state.you_view(world)
        self.actions = web_state.actions_for(self.view)

    def finish(self, error: str | None = None) -> None:
        """The game is over (quit, last minute or a crash). Now the outcome and secret show."""
        with self.cv:
            if self.finished:
                return
            self.error = error or self.error
            if self.world is not None:
                self._refresh(self.world)
                self.outcome, self.secret = web_state.finish_view(self.world, self.sc)
            self.finished, self.awaiting = True, False
            self.cv.notify_all()

    def turn(self, world: World) -> list[Intent] | None:
        with self.cv:
            self._refresh(world)
            if self.wait_left > 0:
                self.wait_left -= 1
                return []  # villagers keep acting, Wren is not asked
            self.awaiting = True
            while not self.inbox and not self.stopped:
                self.cv.wait(POLL_SECONDS)
            self.awaiting = False
            kind, data = self.inbox.popleft() if self.inbox else ("quit", None)
            if kind == "quit":
                self.finish()
                return None
            if kind == "wait":
                self.wait_left = data - 1  # this minute is the first one
                return []
            return [data]

    def report(self, intent: Intent, result: ActionResult) -> None:
        with self.cv:
            self.rejection = None if result.ok else result.reason


def intent_from(body: dict) -> Intent | None:
    """Build Wren's intent from the posted fields, or None if the action is not one she has."""
    if body.get("action") not in ALLOWED:
        return None
    fields = {k: body.get(k) or None for k in ("target", "item", "message")}
    if any(v is not None and not isinstance(v, str) for v in fields.values()):
        return None
    return Intent(actor=PLAYER_ID, action=body["action"], **fields)
