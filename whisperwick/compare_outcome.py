"""Two extra `compare` lines per run: who is held at the end, and how the aims went."""

from whisperwick import outcome

AIM_STATUSES = ("new", "continuing", "done", "dropped")


def aim_counts(log) -> dict[str, int]:
    """How many records had each aim_status. A missing key (older record) counts as nothing."""
    counts = dict.fromkeys(AIM_STATUSES, 0)
    for r in log.records:
        if r.get("aim_status") in counts:
            counts[r["aim_status"]] += 1
    return counts


def aims_text(log) -> str:
    if log is None:
        return "-"  # an older run has no belief log
    return " / ".join(f"{k} {v}" for k, v in aim_counts(log).items())


def lines(runs: list[dict], names: dict[str, str]) -> list[str]:
    """Held-at-end (world events) and aims (belief log), one line per run each."""
    out = ["Held at the end:"]
    out += [f"  {r['name']}: {outcome.held_text(r['events'], names)}" for r in runs]
    out += ["", "Aims (new / continuing / done / dropped):"]
    out += [f"  {r['name']}: {aims_text(r.get('beliefs'))}" for r in runs]
    return out
