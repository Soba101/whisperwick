"""The player's "What I know" journal, built by plain code from the player's own feed.

Nothing here calls a model, reads the world, or knows anything the feed does not say.
Names and places are matched as words in feed lines. Lookups go by id; display names
are only the text we search for. It never says who is right: it shows both lines.
"""

import re
from itertools import combinations

# "09:30", "9:05", "9am", "9 pm". Only the hour is kept: two lines agree on the hour.
CLOCK_OR_AMPM = re.compile(r"\b(\d{1,2}):\d{2}\b|\b(\d{1,2})\s?(am|pm)\b", re.I)


def _find(names: dict[str, str], text: str) -> list[str]:
    """Ids whose display name appears as a whole word in the text, in id order."""
    return [
        i for i, n in sorted(names.items())
        if re.search(rf"\b{re.escape(n)}\b", text, re.I)
    ]  # fmt: skip


def _split(line: str) -> tuple[str, str]:
    """(body, words). Talk lines carry the spoken words after ': "'; others have none."""
    body, sep, words = line.partition(': "')
    return (body, words.rstrip('"')) if sep else (line, "")


def _hours(text: str) -> set[int]:
    """Hours (0-23) named in spoken words. Bare numbers are ignored: too ambiguous."""
    out = set()
    for m in CLOCK_OR_AMPM.finditer(text):
        if m.group(1):
            out.add(int(m.group(1)) % 24)
        else:
            out.add(int(m.group(2)) % 12 + (12 if m.group(3).lower() == "pm" else 0))
    return out


def about_people(feed: list[str], people: dict[str, str], skip: str) -> list[dict]:
    """Feed lines grouped by each person they name. The player is not a subject."""
    groups: dict[str, list[str]] = {}
    for line in feed:
        # Spoken words say who the talk is about; other lines name their actor.
        body, words = _split(line)
        for pid in _find(people, words or body):
            if pid != skip:
                groups.setdefault(pid, []).append(line)
    return [{"id": p, "name": people[p], "lines": groups[p]} for p in sorted(groups)]


def contradictions(feed: list[str], people: dict[str, str], places: dict[str, str],
                   skip: str) -> list[dict]:
    """Two spoken lines about one person and hour that name different places."""
    claims: dict[tuple[str, int], list[tuple[str, str]]] = {}
    for line in feed:
        words = _split(line)[1]
        for hour in _hours(words):
            for pid in _find(people, words):
                for place in _find(places, words):
                    if pid != skip:
                        claims.setdefault((pid, hour), []).append((place, line))
    out = []
    for (pid, hour), rows in sorted(claims.items()):
        for (pa, la), (pb, lb) in combinations(rows, 2):
            if pa != pb and la != lb:
                out.append({"id": pid, "name": people[pid], "hour": f"{hour:02d}:00",
                            "a": la, "b": lb})  # fmt: skip
    return out


def _where(item: dict) -> tuple[str, str]:
    """Where and when we saw it. A gift we saw only in our hands has no ground sighting."""
    if item["carried"] or "place" not in item:
        return item["carried_place"]["name"], item["carried_clock"]
    return item["place"]["name"], item["clock"]


def build(feed: list[str], known: dict, people: dict[str, str], places: dict[str, str],
          player: str) -> dict:
    """The whole journal. `known` is the player's own sightings snapshot."""
    return {
        "about": about_people(feed, people, player),
        "items": [
            {"name": i["name"], "carried": i["carried"],
             "place": _where(i)[0], "clock": _where(i)[1]}
            for i in known["items"]
        ],  # fmt: skip
        "visits": known["visits"],
        "contradictions": contradictions(feed, people, places, player),
    }
