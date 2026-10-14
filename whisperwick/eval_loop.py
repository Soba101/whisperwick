"""The "after arrest" loop measure. Read-only: it only looks at events already logged.

After the last arrest the story can go on (new claims, people moving, things changing) or
loop (the same people repeating the same claims). These numbers show which one happened.
Only villager events count: the player's own actions are not the village looping.
"""

from collections import Counter

from whisperwick.clock import MINUTES_PER_DAY
from whisperwick.player import PLAYER_ID

AWAKE_HOURS = range(6, 22)  # 06:00 to 22:00, when villagers are expected to be active
# Short windows can look like a pass, so require one waking day (06:00-22:00).
MIN_CLAIM_GAP_WINDOW_MINUTES = 16 * 60

NO_LOOP = {
    "longest_claim_gap_hours": None,
    "new_claims_per_day": None,
    "new_claims_after_arrest": None,
    "not_talk_after_arrest": None,
    "events_after_arrest": None,
    "top_pair_share": None,
}


def claim_key(e) -> tuple | None:
    """(speaker, claim kind, claim subject) for a talk with a claim, else None."""
    claim = e.data.get("claim")
    if e.type != "talk" or not claim or not claim.get("kind"):
        return None
    return (e.actor, claim["kind"], claim.get("subject"))


def top_pair_share(talks) -> float | None:
    """Share of talks made by the two most common (speaker, listener) pairs."""
    if not talks:
        return None
    counts = Counter((e.actor, e.data.get("to")) for e in talks)
    # Sort by count, then by pair, so ties always come out the same way.
    top = sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))[:2]
    return sum(n for _, n in top) / len(talks)


def waking_minutes(a: int, b: int) -> int:
    """Minutes between ticks a and b that fall inside waking hours (night is not counted)."""
    return sum((t // 60) % 24 in AWAKE_HOURS for t in range(a, b))


def longest_gap_hours(points: list[int]) -> float:
    """Longest waking stretch between consecutive points (arrest, new claims, run end)."""
    return max(waking_minutes(a, b) for a, b in zip(points, points[1:], strict=False)) / 60


def loop_measures(events, end: int) -> dict:
    """Loop numbers relative to the last arrest (end = run end tick).

    All None when nobody was ever arrested.
    """
    npc = [e for e in events if e.actor != PLAYER_ID]
    arrests = [e.tick for e in npc if e.type == "arrest"]
    if not arrests:
        return dict(NO_LOOP)
    arrest = max(arrests)
    # Claims seen before the arrest count as old; a repeat later is not new.
    seen = {k for e in npc if e.tick <= arrest and (k := claim_key(e))}
    new_ticks = []
    for e in npc:
        k = claim_key(e)
        if e.tick > arrest and k and k not in seen:
            seen.add(k)
            new_ticks.append(e.tick)
    after = [e for e in npc if e.tick > arrest]
    days = (end - arrest) / MINUTES_PER_DAY
    new = len(new_ticks)
    # Points are the arrest, every new claim and the end, so the end closes the last gap.
    points = [arrest, *new_ticks, max(end, arrest)]
    enough_time = waking_minutes(arrest, end) >= MIN_CLAIM_GAP_WINDOW_MINUTES
    return {
        "longest_claim_gap_hours": longest_gap_hours(points) if enough_time else None,
        "new_claims_per_day": new / days if days > 0 else None,
        "new_claims_after_arrest": new,
        # Looking changes nothing, so it does not count as the story moving on.
        "not_talk_after_arrest": sum(e.type not in ("talk", "look") for e in after),
        "events_after_arrest": len(after),
        "top_pair_share": top_pair_share([e for e in after if e.type == "talk"]),
    }
