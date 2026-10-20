"""Small private files shared by the CLI and server, never by the world engine."""

import fcntl
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

_LOCK = threading.RLock()


def now() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def locked(folder: Path):
    # Threads and separate CLI processes must not overwrite each other's changes.
    with _LOCK:
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / ".invites.lock").open("a") as stream:
            os.chmod(stream.name, 0o600)
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def atomic_write(path: Path, text: str) -> None:
    # Readers see either complete version. Temporary files are private from creation.
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".invite-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_rows(path: Path, entries: list[dict]) -> None:
    atomic_write(path, "".join(json.dumps(row) + "\n" for row in entries))


def valid_name(value) -> str:
    # Unicode letters are welcome. Digits, markup and control characters are not.
    if (not isinstance(value, str) or not 1 <= len(value) <= 40 or not value.strip()
            or any(not (c.isalpha() or c in " .'-") for c in value)):
        raise ValueError("Name must be 1-40 characters: letters, spaces, . ' or -.")
    return value.strip()
