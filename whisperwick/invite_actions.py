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
    # Validate the destination before minting a secret that cannot be recovered.
    key = store.invite(name, approve)
    return f"{'https' if secure else 'http'}://{host}/?key={key}"
