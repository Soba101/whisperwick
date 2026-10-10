"""Everything the replay page needs, as plain JSON-ready data. World facts only.

The scenario secret and the belief log are never read here. The one optional extra,
private thoughts, is passed in as its own list and clearly labelled in the page.
"""

import json

from whisperwick.claims import claim_words
from whisperwick.events import Event
from whisperwick.replay_state import layout
from whisperwick.scenario import Scenario
from whisperwick.story import names_from

SHOWN = {"talk", "move", "take", "drop", "give", "show", "arrest", "release"}


def event_row(e: Event, names: dict[str, str]) -> dict:
    """One event, trimmed to what the feed and the replay use."""
    row = {"id": e.id, "tick": e.tick, "type": e.type, "actor": e.actor, "loc": e.location}
    d = e.data
    if e.type == "talk":
        row["to"], row["text"] = d["to"], d["message"]
        if claim := d.get("claim"):
            tag = claim_words(claim, names.get(claim["subject"], claim["subject"]))
            row["claim"] = tag + (" (unverified tag)" if claim.get("unverified") else "")
    elif e.type == "move":
        row["to"] = d["to"]
    elif e.type in ("take", "drop", "give", "show"):
        row["item"], row["to"] = d["item_name"], d.get("to")
    else:  # arrest, release
        row["to"], row["text"] = d["target"], d.get("reason", "")
    return row


def build_data(
    scenario: Scenario,
    events: list[Event],
    label: str = "",
    thoughts: list[dict] | None = None,
) -> dict:
    """The one dict embedded in the page."""
    names = names_from(scenario)
    spots = layout(scenario)
    start = scenario.start
    return {
        "label": label,
        "start": (start["day"] - 1) * 1440 + start["hour"] * 60,
        "end": max([e.tick for e in events], default=0),
        "places": [
            {"id": p.id, "name": p.name, "x": spots[p.id][0], "y": spots[p.id][1], "links": p.links}
            for p in scenario.locations
        ],
        "people": [
            {"id": n.id, "name": n.name, "loc": n.location, "alive": n.alive} for n in scenario.npcs
        ],
        "names": names,
        "events": [event_row(e, names) for e in events if e.type in SHOWN],
        "thoughts": thoughts or [],
    }


def to_json(data: dict) -> str:
    """JSON safe inside a script tag: '<' becomes \\u003c, so '</script>' cannot break out."""
    return json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")
