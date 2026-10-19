"""Play entry points. Entropy picks only the crime number, before world creation."""

import os

from whisperwick.crime import generate
from whisperwick.scenario import load_scenario


def crime_number(value: str | int) -> int:
    if value == "random":
        return int.from_bytes(os.urandom(4), "big")
    # Reject booleans, floats, signs and huge request bodies consistently.
    text = str(value)
    if not text.isascii() or not text.isdecimal() or len(text) > 20:
        raise ValueError("crime must be random or a nonnegative crime number (up to 20 digits)")
    return int(text)


def select(scenario, crime=None):
    # This branch preserves the old load exactly and draws no random numbers.
    return load_scenario(scenario) if crime is None else generate(crime_number(crime))
