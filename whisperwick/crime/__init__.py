"""Seeded starting crimes. The generator never runs during a game."""

from whisperwick.crime.check import check
from whisperwick.crime.generate import generate

__all__ = ["check", "generate"]
