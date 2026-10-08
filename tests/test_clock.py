"""Clock tests: time labels and no time travel."""

import pytest

from whisperwick.clock import Clock


def test_label_day_and_time():
    assert Clock.at(day=2, hour=8, minute=5).label() == "day 2 08:05"


def test_advance_moves_forward():
    clock = Clock.at(1, 23, 59)
    clock.advance()
    assert clock.label() == "day 2 00:00"


def test_time_cannot_go_backwards():
    with pytest.raises(ValueError):
        Clock().advance(-1)
