"""Bounded waiting requests. Nothing here grants access or records IP addresses."""

import hashlib
import re
import secrets
import threading
import time
from collections import deque
from pathlib import Path

from whisperwick.invite_files import locked, now, rows, valid_name, write_rows

# A request ticket doubles as the "come back later" code (2026-10-21). No 0/O/1/I, so it can
# be typed from another device. 10 characters of 32 is 50 bits: far beyond guessing at the
# form's limit of 10 tries a minute. Only its hash is stored.
CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_RE = re.compile(r"[A-HJ-NP-Z2-9]{10}")


def new_code() -> str:
    return "".join(secrets.choice(CODE_LETTERS) for _ in range(10))


def clean_code(code) -> str | None:
    """Accept 'k7pq-m2xd-ab' style input; None when it cannot be a code."""
    text = re.sub(r"[\s-]", "", code).upper() if isinstance(code, str) else ""
    return text if CODE_RE.fullmatch(text) else None


def ticket_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


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

    def waiting(self, code: str | None) -> bool:
        """Is this ticket's request still waiting for the owner?"""
        if not code:
            return False
        digest = ticket_hash(code)
        with locked(self.folder):
            return any(r.get("ticket_hash") == digest for r in rows(self.path))

    def save(self, body: dict) -> tuple[int, str, str | None]:
        """Status, message and the requester's code. The answer looks the same for a new
        name and a repeat, but only the first request's code is ever tied to the request:
        sending someone else's name again cannot take over their approval."""
        try:
            name = valid_name(body.get("name"))
            note = body.get("note", "")
            if set(body) - {"name", "note"} or not isinstance(note, str) or len(note) > 300:
                raise ValueError("Note must be at most 300 characters.")
        except ValueError as e:
            return 400, str(e), None
        code = new_code()
        try:
            with locked(self.folder):
                waiting = rows(self.path)
                # A full queue gives the same response for every name, including duplicates.
                full = len(waiting) >= 20
                match = next((r for r in waiting if r["name"].casefold() == name.casefold()), None)
                if match is None and not full:
                    waiting.append({"time": now(), "name": name, "note": note,
                                    "ticket_hash": ticket_hash(code)})
                elif match is not None:
                    match["note"] = note
                write_rows(self.path, waiting)
                if full:
                    return 429, "The waiting list is full. Please try again later.", None
        except OSError:
            return 500, "Could not save request. Please try again.", None
        return 200, "Request sent", code
