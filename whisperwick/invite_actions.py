"""Link creation shared by the terminal and owner page. Secrets are returned only once."""

import json
import re

from whisperwick.invite_players import Players


def invite_link(store: Players, name: str, approve: bool = False,
                host: str | None = None, secure: bool = True) -> str:
    default = store.folder / "invite-host.json"
    host = host or (json.loads(default.read_text()) if default.exists() else "YOUR-HOST")
    if not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]{1,5})?", host):
        raise ValueError("Use a host name, optionally with a port.")
    # Validate the destination before minting a secret.
    key = store.invite(name, approve)
    return link_for(host, key, secure)


def link_for(host: str | None, key: str, secure: bool = True) -> str:
    """A player's personal link. The owner page rebuilds it from the stored key."""
    return f"{'https' if secure else 'http'}://{host or 'YOUR-HOST'}/?key={key}"
