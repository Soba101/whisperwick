"""Public scene presentation facts shared by both pages. No private world data."""

import math

from whisperwick.actions import MAX_MESSAGE_CHARS
from whisperwick.player import PLAYER_ID
from whisperwick.web_guide import HOOK


def presentation(player) -> dict:
    # Only a currently visible person may acquire a waiting label or bubble.
    people = {p["id"]: p["name"] for p in player.view.get("people", [])}
    visible = {PLAYER_ID, *people}
    tick = player.world.clock.tick if player.world else 0
    daylight = max(0, math.sin((tick % 1440 - 360) * math.pi / 720))
    return {
        "player": {"id": PLAYER_ID, "name": "Wren"},
        "hook": HOOK,
        "message_limit": MAX_MESSAGE_CHARS,
        "daylight": round(daylight, 3),
        "waiting_on": people.get(player.waiting_on),
        "turn_of": people.get(player.turn_of[0]) if player.turn_of else None,
        "reply_to": player.reply_to if player.reply_to and player.reply_to["id"] in people
                    else None,
        "motions": list(player.motions.values()),
        "interactions": [v for k, v in player.interactions.items() if k in visible],
        "speech": {k: v for k, v in player.speech.items() if k in visible},
    }


def walk(world, event, sequence: int) -> dict:
    """Only called after the existing player feed has accepted the move event."""
    return {"id": event.actor, "name": world.npcs[event.actor].name,
            "from": event.data["from"], "to": event.data["to"], "sequence": sequence}
