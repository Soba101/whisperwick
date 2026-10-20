"""Bounded waiting requests. Nothing here grants access or records IP addresses."""

import threading
import time
from collections import deque
from pathlib import Path

from whisperwick.invite_files import locked, now, rows, valid_name, write_rows


class Requests:
    def __init__(self, folder: Path, clock=time.monotonic):
        self.folder, self.clock = folder, clock
        self.path = folder / "requests.jsonl"
        self.lock = threading.Lock()
        self.attempts = deque()

    def allow(self) -> bool:
        # Count every POST attempt, including malformed bodies. No client identity is needed.
        with self.lock:
            tick = self.clock()
            while self.attempts and self.attempts[0] <= tick - 60:
                self.attempts.popleft()
            if len(self.attempts) >= 10:
                return False
            self.attempts.append(tick)
            return True

    def decline(self, name: str) -> None:
        name = valid_name(name)
        with locked(self.folder):
            waiting = rows(self.path)
            kept = [r for r in waiting if r["name"].casefold() != name.casefold()]
            if len(kept) == len(waiting):
                raise ValueError("No waiting request for that name.")
            write_rows(self.path, kept)

    def save(self, body: dict) -> tuple[int, str]:
        try:
            name = valid_name(body.get("name"))
            note = body.get("note", "")
            if set(body) - {"name", "note"} or not isinstance(note, str) or len(note) > 300:
                raise ValueError("Note must be at most 300 characters.")
        except ValueError as e:
            return 400, str(e)
        try:
            with locked(self.folder):
                waiting = rows(self.path)
                # A full queue gives the same response for every name, including duplicates.
                full = len(waiting) >= 20
                match = next((r for r in waiting if r["name"].casefold() == name.casefold()), None)
                if match is None and not full:
                    waiting.append({"time": now(), "name": name, "note": note})
                elif match is not None:
                    match["note"] = note
                write_rows(self.path, waiting)
                if full:
                    return 429, "The waiting list is full. Please try again later."
        except OSError:
            return 500, "Could not save request. Please try again."
        return 200, "Request sent"
