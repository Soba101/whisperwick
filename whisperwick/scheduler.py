"""The scheduler: decides WHO gets a model call this tick.

Pure code, no randomness, no model. Same inputs give the same list.
A model call is slow, so most NPCs most minutes should NOT be asked anything.
"""

from whisperwick.clock import MINUTES_PER_DAY
from whisperwick.events import Event

ROUTINE_EVERY = 60  # minutes: even a quiet NPC gets a turn this often
# Minimum minutes between two decisions by one NPC. It now only slows routine and
# overheard wake-ups (stops idle ping-pong between bystanders). Someone spoken to
# skips it: they answer next minute.
COOLDOWN = 5
# A speaker waits this long for an answer, then gives up (the other side went quiet,
# or chose to leave without a word).
ANSWER_WAIT = 5  # minutes
SLEEP_START = 22  # hour of day when the village goes to bed
SLEEP_END = 6  # hour of day when it wakes up


class Scheduler:
    def __init__(self, npc_ids):
        # None means "never decided yet", so a fresh NPC is due straight away.
        self.last: dict[str, int | None] = {npc_id: None for npc_id in npc_ids}
        # NPCs that something happened to since their last decision.
        self.woken: set[str] = set()
        # Spoken to: npc -> first tick it may answer (the minute after the talk).
        self.answer_at: dict[str, int] = {}
        # Speaker -> (who it spoke to, tick it spoke). It is not asked again until the
        # other side does anything, or ANSWER_WAIT passes.
        self.waiting: dict[str, tuple[str, int]] = {}
        # Reasons describe the latest due list, even if events arrive while it acts.
        self.reasons: dict[str, str] = {}

    def notice(self, event: Event) -> None:
        """Wake whoever an event is about: the talk, give or show target and every witness.

        The actor is skipped: it just acted, so it does not need a new turn for that.
        """
        affected = set(event.witnesses)
        # A show with no target is for everyone here, so "to" can be None: skip it then.
        if event.type in ("talk", "give", "show") and event.data.get("to"):
            affected.add(event.data["to"])
        affected.discard(event.actor)
        # Ignore ids we do not schedule. A stray id must never create a turn.
        self.woken |= affected & self.last.keys()
        # Anyone waiting on the actor got something back: stop waiting.
        for npc_id in [n for n, (to, _) in self.waiting.items() if to == event.actor]:
            del self.waiting[npc_id]
        to = event.data.get("to")
        if event.type == "talk" and to:
            if to in self.last and to != event.actor:
                # Spoken to: answer next minute, cooldown or not. Being spoken to
                # also beats any wait of its own.
                self.answer_at[to] = event.tick + 1
                self.waiting.pop(to, None)
            if event.actor in self.last and to != event.actor:
                # The speaker waits for the answer. "to" may be the player.
                self.waiting[event.actor] = (to, event.tick)

    def asleep(self, tick: int) -> bool:
        """True from 22:00 until 06:00."""
        hour = tick % MINUTES_PER_DAY // 60
        return hour >= SLEEP_START or hour < SLEEP_END

    def due(self, tick: int) -> list[str]:
        """Sorted ids that should get a model call now."""
        self.reasons.clear()
        if self.asleep(tick):
            # Night is quiet. Wake-ups are dropped, not saved for the morning: the murder
            # at night is injected by the scenario, not by agents.
            # Pending answers and waits go the same way: nobody carries a talk to bed.
            self.woken.clear()
            self.answer_at.clear()
            self.waiting.clear()
            return []
        ready = []
        for npc_id in sorted(self.last):
            if npc_id in self.answer_at:
                if tick >= self.answer_at[npc_id]:
                    ready.append(npc_id)  # spoken to: no cooldown, no wait
                    self.reasons[npc_id] = "answer"
                continue
            if npc_id in self.waiting:
                if tick - self.waiting[npc_id][1] < ANSWER_WAIT:
                    continue  # still hoping for an answer: no routine or wake-up turn
                del self.waiting[npc_id]  # gave up
            last = self.last[npc_id]
            if last is not None and tick - last < COOLDOWN:
                continue  # decided too recently, even if woken
            if last is None or npc_id in self.woken or tick - last >= ROUTINE_EVERY:
                ready.append(npc_id)
                # Label only after selection, so priority cannot change who acts.
                self.reasons[npc_id] = (
                    "woken" if npc_id in self.woken else "first" if last is None else "routine"
                )
        return ready

    def acted(self, npc_id: str, tick: int) -> None:
        """Record a decision. The NPC is no longer waiting on whatever woke it."""
        self.last[npc_id] = tick
        self.woken.discard(npc_id)
        self.answer_at.pop(npc_id, None)
