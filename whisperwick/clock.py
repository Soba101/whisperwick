"""The game clock.

One tick = one game minute. Ticks are plain integers, so time is easy to
store, compare and replay. Day 1 starts at tick 0 (midnight).
"""

from dataclasses import dataclass

MINUTES_PER_DAY = 24 * 60


@dataclass
class Clock:
    # Minutes since midnight on day 1.
    tick: int = 0

    @classmethod
    def at(cls, day: int, hour: int, minute: int = 0) -> "Clock":
        """Build a clock set to a given day and time. Days start at 1."""
        return cls((day - 1) * MINUTES_PER_DAY + hour * 60 + minute)

    def advance(self, minutes: int = 1) -> None:
        """Move time forward. Time never goes backwards."""
        if minutes < 0:
            raise ValueError("time cannot go backwards")
        self.tick += minutes

    @property
    def day(self) -> int:
        return self.tick // MINUTES_PER_DAY + 1

    def label(self) -> str:
        """Human-readable time, e.g. 'day 1 08:05'. Used in logs and the CLI."""
        minutes_today = self.tick % MINUTES_PER_DAY
        return f"day {self.day} {minutes_today // 60:02d}:{minutes_today % 60:02d}"
