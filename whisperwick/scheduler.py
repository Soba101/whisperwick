"""The scheduler: decides WHO gets a model call this tick.

Pure code, no randomness, no model. Same inputs give the same list.
A model call is slow, so most NPCs most minutes should NOT be asked anything.
"""

from whisperwick.clock import MINUTES_PER_DAY
from whisperwick.events import Event

ROUTINE_EVERY = 60  # minutes: even a quiet NPC gets a turn this often
COOLDOWN = 5  # minimum minutes between two decisions by one NPC (stops talk ping-pong)
SLEEP_START = 22  # hour of day when the village goes to bed
SLEEP_END = 6  # hour of day when it wakes up


class Scheduler:
    def __init__(self, npc_ids):
        # None means "never decided yet", so a fresh NPC is due straight away.
        self.last: dict[str, int | None] = {npc_id: None for npc_id in npc_ids}
        # NPCs that something happened to since their last decision.
        self.woken: set[str] = set()

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

    def asleep(self, tick: int) -> bool:
        """True from 22:00 until 06:00."""
        hour = tick % MINUTES_PER_DAY // 60
        return hour >= SLEEP_START or hour < SLEEP_END

    def due(self, tick: int) -> list[str]:
        """Sorted ids that should get a model call now."""
        if self.asleep(tick):
            # Night is quiet. Wake-ups are dropped, not saved for the morning: the murder
            # at night is injected by the scenario, not by agents.
            self.woken.clear()
            return []
        ready = []
        for npc_id in sorted(self.last):
            last = self.last[npc_id]
            if last is not None and tick - last < COOLDOWN:
                continue  # decided too recently, even if woken
            if last is None or npc_id in self.woken or tick - last >= ROUTINE_EVERY:
                ready.append(npc_id)
        return ready

    def acted(self, npc_id: str, tick: int) -> None:
        """Record a decision. The NPC is no longer waiting on whatever woke it."""
        self.last[npc_id] = tick
        self.woken.discard(npc_id)
