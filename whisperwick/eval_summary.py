"""The summary under the per-run tables: divergence, and memory on versus off."""

from whisperwick.compare import table
from whisperwick.eval_format import num, pct


def held_key(m: dict) -> tuple:
    """A run's end outcome as something comparable: the set of people held."""
    return tuple(sorted(m["held"]))


def divergence(ms: list[dict]) -> list[str]:
    """Per seed, how many different end outcomes appear across player scripts.

    Runs with no recorded seed (older runs) are treated as one group.
    """
    by_seed: dict = {}
    for m in ms:
        by_seed.setdefault(m["seed"], []).append(m)
    rows = [["Seed", "Runs", "Scripts", "Distinct outcomes"]]
    comparable = differ = 0
    for seed, group in sorted(by_seed.items(), key=lambda kv: str(kv[0])):
        scripts = {m["script"] for m in group}
        distinct = {held_key(m) for m in group}
        rows.append(["-" if seed is None else str(seed), str(len(group)), str(len(scripts)),
                     str(len(distinct))])  # fmt: skip
        # Only a seed with two or more scripts can show a script making a difference.
        if len(scripts) > 1:
            comparable += 1
            differ += len(distinct) > 1
    share = f"{differ}/{comparable} = {pct(differ / comparable)}" if comparable else "n/a"
    return [*table(rows), f"Seeds where the outcome differs by script: {share}"]


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def memory_rows(ms: list[dict]) -> list[str]:
    """Averages of the main measures, memory on versus off."""
    rows = [["Memory", "Runs", "Rejected", "Talk", "Sourced", "Arrests", "Stalls", "Aims new",
             "Right"]]  # fmt: skip
    for flag, label in ((True, "on"), (False, "off")):
        g = [m for m in ms if m["memory"] is flag]
        if not g:
            continue
        sourced = [m["valid_share"] for m in g if m["valid_share"] is not None]
        rows.append([label, str(len(g)), pct(mean([m["rejection"] for m in g])),
                     pct(mean([m["talk_share"] for m in g])), pct(mean(sourced)),
                     num(mean([m["arrests"] for m in g])), num(mean([m["stalls"] for m in g])),
                     num(mean([m["aims"]["new"] for m in g])),
                     pct(mean([m["verdict"] == "right" for m in g]))])  # fmt: skip
    return table(rows)
