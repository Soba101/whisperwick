"""The web player: the page sends one action or a wait, the run loop picks it up.

The run loop runs in its own thread and owns the world (its database connection is
bound to that thread). So the world is read ONLY from that thread, inside turn() and
finish(), and the result is kept as plain data. The server threads only read that data
under the lock. That way the page can never see more than Wren could see.
"""

import threading
from collections import deque

from whisperwick import player_terminal, web_silence, web_state
from whisperwick.actions import ActionResult, Intent
from whisperwick.player import PLAYER_ID, PlayerSource
from whisperwick.scenario import Scenario
from whisperwick.web_known import Known
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


class WebPlayer(PlayerSource):
    def __init__(self, sc: Scenario):
        self.sc = sc
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
                "clock": world.clock.label() if world else "",
                "you": self.view,
                "known": self.known.snapshot(),
                "actions": self.actions,
                "places": self.places,
                "awaiting": self.awaiting and not self.finished,
                "auto_wait": self.auto_left > 0 and not self.awaiting and not self.finished,
                "busy": "" if self.awaiting or self.finished else self.busy,
                "finished": self.finished,
                "rejection": self.rejection,
                "feed": self.feed[since:],
                "feed_total": len(self.feed),
                "outcome": self.outcome,
                "secret": self.secret,
                "error": self.error,
            }

    # ---- called from the run loop thread ----

    def _catch_up(self, world: World) -> None:
        """Add feed lines for log events not looked at yet. Safe to call at any time:
        it goes by position in the log, so no event is ever added twice. Lock held."""
        events = world.log.all()
        fresh, self.seen = events[self.seen :], len(events)
        for event in fresh:
            lines = player_terminal.player_lines(world, [event], claims=False)  # words only
            self.feed += lines
            self.lines_by[event.actor] = self.lines_by.get(event.actor, 0) + len(lines)
            if lines and event.actor != PLAYER_ID:
                self.others += 1  # something Wren can see that someone else did or said

    def _close_turn(self, world: World) -> None:
        """Show a quiet reply after the villager's real turn has finished. Lock held."""
        if self.turn_of is None:
            return
        npc_id, errors, lines, tick = self.turn_of
        self.turn_of, self.waiting_on = None, None
        if self.lines_by.get(npc_id, 0) > lines:
            return  # Its real action is already visible.
        if world.npcs[npc_id].location == world.npcs[PLAYER_ID].location:
            errored = self.stats.get("errors", 0) > errors
            self.feed.append(web_silence.silence_line(world, npc_id, errored, tick))
            self.others += 1  # A quiet reply also gives Wren her turn back.
            self.lines_by[npc_id] = lines + 1

    def _refresh(self, world: World) -> None:
        """Take a new picture of what Wren sees. Lock held by the caller."""
        self.world = world
        self._catch_up(world)
        self._close_turn(world)
        self.view = web_state.you_view(world)
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
            self.finished, self.awaiting = True, False
            self.cv.notify_all()

    def on_event(self, world: World, event) -> None:
        """Run-loop hook: a villager event was just applied. Show it now if Wren may see it."""
        with self.cv:
            self._catch_up(world)  # the event is already in the log; same filter as always

    def on_turn(self, world: World, npc_id: str | None) -> None:
        """Run-loop hook: a model call starts (npc_id None = the day's thinking phase).

        The label names a villager only when that villager is where Wren is, so the
        page never shows who is where outside Wren's view.
        """
        with self.cv:
            self._catch_up(world)  # also shows Wren's own action right away
            self._close_turn(world)
            if npc_id is not None and npc_id == self.waiting_on:
                # The tick is kept: the turn is closed later, often after the clock has moved on.
                self.turn_of = (npc_id, self.stats.get("errors", 0), self.lines_by.get(npc_id, 0),
                                world.clock.tick)
            if npc_id is None:
                self.busy = "The villagers are thinking about the day..."
            elif world.npcs[npc_id].location == world.npcs[PLAYER_ID].location:
                self.busy = f"{world.npcs[npc_id].name} is thinking..."
            else:
                self.busy = "Someone elsewhere is acting..."

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
