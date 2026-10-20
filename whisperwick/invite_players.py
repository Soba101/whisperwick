"""Personal keys: hashes on disk, with revocation checked on the next request."""

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

from whisperwick.invite_files import atomic_write, locked, now, rows, valid_name, write_rows


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class Players:
    def __init__(self, folder: Path):
        self.folder = folder
        self.path = folder / "players.json"
        self._stamp = None
        self._players = []
        self._seen = {}

    def read(self) -> list[dict]:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []

    def write(self, players: list[dict]) -> None:
        atomic_write(self.path, json.dumps(players, indent=2) + "\n")

    def authenticate(self, key: str | None) -> str | None:
        if not key:
            return None
        # A rename changes the inode too. Do not keep accepting cached keys on read errors.
        with locked(self.folder):
            try:
                stat = self.path.stat()
                stamp = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
                if stamp != self._stamp:
                    players = self.read()
                    self._players, self._stamp = players, stamp
                digest = key_hash(key)
                for player in self._players:
                    matches = hmac.compare_digest(digest, player["key_hash"])
                    if matches and not player["revoked"]:
                        return player["name"]
            except (OSError, ValueError, KeyError, TypeError):
                self._players, self._stamp = [], None
        return None

    def invite(self, name: str, approve: bool = False) -> str:
        name = valid_name(name)
        if name.casefold() == "owner":
            raise ValueError("The name owner is reserved.")
        with locked(self.folder):
            players = self.read()
            if any(p["name"].casefold() == name.casefold() for p in players):
                raise ValueError("Player already exists; revoke does not issue a new key.")
            path = self.folder / "requests.jsonl"
            waiting = rows(path)
            match = next((r for r in waiting if r["name"].casefold() == name.casefold()), None)
            if approve and match is None:
                raise ValueError("No waiting request for that name.")
            key = secrets.token_urlsafe(32)
            players.append({"name": name, "key_hash": key_hash(key), "created": now(),
                            "last_seen": None, "games": 0, "revoked": False})
            self.write(players)
            write_rows(path, [r for r in waiting if r is not match])
            return key

    def revoke(self, name: str) -> str:
        with locked(self.folder):
            players = self.read()
            player = next((p for p in players if p["name"].casefold() == name.casefold()), None)
            if player is None:
                raise ValueError("No such player.")
            player["revoked"] = True
            self.write(players)
            return player["name"]  # the stored spelling, for stopping that player's game

    def visit(self, name: str, new_game: bool = False) -> None:
        with locked(self.folder):
            tick = time.monotonic()
            # Polling can happen every second. Save last_seen at most once a minute.
            if not new_game and tick - self._seen.get(name, float("-inf")) < 60:
                return
            players = self.read()
            for player in players:
                if player["name"] == name and not player["revoked"]:
                    player["last_seen"] = now()
                    player["games"] += int(new_game)
                    self.write(players)
                    self._seen[name] = tick
                    break
