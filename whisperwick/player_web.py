"""The web player: the page sends one action or a wait, the run loop picks it up.

The run loop runs in its own thread and owns the world (its database connection is
bound to that thread). So the world is read ONLY from that thread, inside turn() and
finish(), and the result is kept as plain data. The server threads only read that data
under the lock. That way the page can never see more than Wren could see.
"""

import threading
from collections import deque

from whisperwick import web_scene, web_state
from whisperwick.actions import ActionResult, Intent
from whisperwick.player import PLAYER_ID, PlayerSource
from whisperwick.player_ending import PlayerEnding
from whisperwick.scenario import Scenario
from whisperwick.web_known import Known
from whisperwick.web_player_feed import WebPlayerFeed
from whisperwick.world import World

# Actions the page may send. Arrest and release are for the authority, not for Wren.
ALLOWED = ("move", "look", "talk", "take", "drop", "give", "show")
WAIT_CHOICES = (10, 60)  # minutes
# After Wren acts, she waits on her own for a reply. Whoever she speaks to is asked
# again the next minute (no cooldown), so a reply is quick; 10 minutes still keeps
# her from being stuck if nobody ever answers.
AUTO_WAIT_MAX = 10  # minutes
NIGHT_START = 22 * 60  # villagers sleep from 22:00 to 06:00
NIGHT_END = 6 * 60
POLL_SECONDS = 0.2  # how often turn() looks up, so quit and stop are noticed


class WebPlayer(WebPlayerFeed, PlayerSource):
    def __init__(self, sc: Scenario):
        self.sc = sc
        self.ending = PlayerEnding(sc)
        self.cv = threading.Condition()  # guards everything below
        self.inbox: deque = deque()  # ("act", Intent), ("wait", minutes) or ("quit", None)
        self.awaiting = False  # True only while turn() is blocked, waiting for Wren
        self.stopped = False
        self.finished = False
        self.wait_left = 0  # quiet minutes still to pass before the next prompt
        self.auto_left = 0  # minutes of automatic waiting left after Wren's last action
        self.others = 0  # lines Wren can see that she did not cause (counted as they arrive)
        self.others_at_act = 0  # that count when she last acted
        self.rejection: str | None = None  # the engine's reason for the last refused action
        self.stats: dict = {}  # Shared with the run loop to detect a failed model call.
        self.waiting_on: str | None = None
        self.turn_of: tuple | None = None  # Actor, starting errors, starting feed count, tick.
        self.lines_by: dict[str, int] = {}
        self.feed: list[str] = []
        self.interactions: dict[str, dict] = {}  # Only witnessed item gestures.
        self.motions: dict[str, dict] = {}  # Only witnessed walks, never hidden positions.
        self.speech: dict[str, str] = {}  # Only lines already allowed into the feed.
        self.seen = 0  # how many log events were already looked at for the feed
        self.busy = ""  # what the page says while the villagers act (never names strangers)
        self.known = Known()
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
            # Quit is also taken while Wren is quietly waiting, so she can always leave.
            quiet = kind == "quit" and (self.auto_left > 0 or self.wait_left > 0)
            if not (self.awaiting or quiet) or self.finished or self.stopped:
                return False
            self.inbox.append((kind, data))
            self.awaiting = False  # the page shows "villagers are acting" at once
            self.busy = ""
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
                **web_scene.presentation(self),
                "clock": world.clock.label() if world else "",
                "you": self.view,
                "known": {**self.known.snapshot(),
                          **({"private_fact": self.sc.private_fact}
                             if self.sc.private_fact else {})},
                **self.ending.snapshot(self.known.snapshot()["people"]),
                "actions": self.actions,
                "places": self.places,
                "awaiting": self.awaiting and not self.finished,
                "auto_wait": self.auto_left > 0 and not self.awaiting and not self.finished,
                "busy": "" if self.awaiting or self.finished else self.busy,
                "finished": self.finished,
                "rejection": self.rejection,
                "feed": self.feed[since:],
                "feed_total": len(self.feed),
                "outcome": self.outcome if self.ending.accusation is not None else None,
                "secret": self.secret if self.ending.accusation is not None else None,
                "error": self.error,
            }

    # ---- called from the run loop thread ----

    def _refresh(self, world: World) -> None:
        """Take a new picture of what Wren sees. Lock held by the caller."""
        self.world = world
        self._catch_up(world)
        self._close_turn(world)
        self.view = web_state.you_view(world, self.sc.player_title)
        self.known.update(self.view)
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
                self.ending.finish(self.world.log.all())
            self.finished, self.awaiting = True, False
            self.cv.notify_all()

    def turn(self, world: World) -> list[Intent] | None:
        with self.cv:
            self._refresh(world)
            if self.wait_left > 0 or self.auto_left > 0:
                if self.inbox and self.inbox[0][0] == "quit" or self.stopped:
                    self.inbox.clear()
                    self.finish()
                    return None
            if self.wait_left > 0:
                self.wait_left -= 1
                return []  # villagers keep acting, Wren is not asked
            if self.auto_left > 0 and self._keep_auto_waiting(world):
                self.auto_left -= 1
                return []  # Wren spoke or acted; give the others time to answer
            self.auto_left = 0
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
            self.auto_left = AUTO_WAIT_MAX  # she acted: wait for a reply before asking again
            self.others_at_act = self.others
            self.waiting_on = data.target if data.action == "talk" else None
            return [data]

    def _keep_auto_waiting(self, world: World) -> bool:
        """True until someone else is seen or heard, it is night, or the time is up."""
        minute = world.clock.tick % 1440
        night = minute >= NIGHT_START or minute < NIGHT_END
        return self.others == self.others_at_act and not night

    def report(self, intent: Intent, result: ActionResult) -> None:
        with self.cv:
            self.rejection = None if result.ok else result.reason
            if not result.ok:
                self.auto_left = 0  # show the reason now, do not wait


def intent_from(body: dict) -> Intent | None:
    """Build Wren's intent from the posted fields, or None if the action is not one she has."""
    if body.get("action") not in ALLOWED:
        return None
    fields = {k: body.get(k) or None for k in ("target", "item", "message")}
    if any(v is not None and not isinstance(v, str) for v in fields.values()):
        return None
    return Intent(actor=PLAYER_ID, action=body["action"], **fields)
