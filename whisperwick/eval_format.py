"""Text tables for `whisperwick eval`: one row per run, then a summary. Plain text."""

from whisperwick.compare import table


def pct(x: float | None) -> str:
    return "-" if x is None else f"{x:.0%}"


def held_cell(m: dict, names: dict[str, str]) -> str:
    held = ", ".join(names.get(h, h) for h in m["held"]) or "nobody"
    return f"{held} ({m['verdict']})"


def recalls_cell(m: dict) -> str:
    r = m["recalls"]
    return "-" if r is None else f"{r.get('act', 0)}/{r.get('think', 0)}"


def run_rows(ms: list[dict], names: dict[str, str]) -> list[str]:
    rows = [["Run", "Script", "Seed", "Memory", "Days", "Held (vs secret)"]]
    for m in ms:
        seed = "-" if m["seed"] is None else str(m["seed"])
        rows.append([m["name"], m["script"], seed, "on" if m["memory"] else "off",
                     f"{m['days']:.1f}", held_cell(m, names)])  # fmt: skip
    return table(rows)


def measure_rows(ms: list[dict]) -> list[str]:
    rows = [["Run", "Calls", "Rejected", "Talk", "Recalls a/t", "Sourced", "BadCite",
             "Aims n/d/x", "Arrest", "Release", "Stalls"]]  # fmt: skip
    for m in ms:
        a = m["aims"]
        rows.append([m["name"], str(m["calls"]), pct(m["rejection"]), pct(m["talk_share"]),
                     recalls_cell(m), pct(m["valid_share"]), str(m["bad_citations"]),
                     f"{a['new']}/{a['done']}/{a['dropped']}", str(m["arrests"]),
                     str(m["releases"]), str(m["stalls"])])  # fmt: skip
    return table(rows)


def judge_rows(ms: list[dict]) -> list[str]:
    """Judge numbers, only for runs that have a .judge.json file."""
    rows = [["Run", "Claims ok", "Support", "Support>=3", "Misreads", "Coherence"]]
    for m in ms:
        s = (m["judge"] or {}).get("summary")
        if s:
            coh = s.get("coherence_by_day") or {}
            mean = f"{sum(coh.values()) / len(coh):.1f}" if coh else "-"
            rows.append([m["name"], pct(s.get("claim_agreement")), num(s.get("support_mean")),
                         pct(s.get("support_ok")), pct(s.get("misread_rate")), mean])  # fmt: skip
    return table(rows) if len(rows) > 1 else []


def num(x: float | None) -> str:
    return "-" if x is None else f"{x:.2f}"
