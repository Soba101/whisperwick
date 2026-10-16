"""Combine per-turn code facts and run a picked list only after its sources pass."""

from collections import Counter

from whisperwick.call_usage import UsageRecorder
from whisperwick.screen_replay import check, difference, replay
from whisperwick.screen_score import score


def ratio(a, b):
    """Leave rates undefined when there were no opportunities to measure them."""
    return a / b if b else None


def totals(records):
    """Combine raw counts before calculating rates across different turn kinds."""
    acts = [r for r in records if r["kind"] == "act"]
    thoughts = [r for r in records if r["kind"] == "think"]
    counts = Counter(dict.fromkeys(("calls", "rejected", "repeats", "errors", "recalls"), 0))
    errors, reasons, thought_errors = Counter(), Counter(), Counter()
    usage = UsageRecorder()
    for r in records:
        counts.update({k: r["stats"].get(k, 0) for k in
                       ("calls", "rejected", "repeats", "errors", "recalls")})
        errors.update(r["stats"].get("error_reasons", {}))
        thought_errors.update(r["stats"].get("thought_error_reasons", {}))
        reasons.update(r["rejection_reasons"])
        # Repeat checks happen before world.act, so they have their own stable label.
        reasons["repeat guard"] += r["stats"].get("repeats", 0)
        # Reuse normal usage accounting so screen costs stay comparable to runs.
        for request in r["requests"]:
            values = dict(request)
            usage.record(values.pop("seconds"), values.pop("reason"), **values)
    costs = usage.summary()
    parsed_thoughts = sum(r["thought_parse_ok"] for r in thoughts)
    # Act stats count parse failures even when the safe look passes the engine.
    parse_failed = sum(r["parse_failed"] for r in records)
    return {
        "turns": len(records), "act_turns": len(acts), "thought_turns": len(thoughts),
        **dict(counts), "parse_rate": ratio(costs["requests"] - parse_failed, costs["requests"]),
        "parse_ok": costs["requests"] - parse_failed, "parse_failed": parse_failed,
        "first_try_accepted": sum(r["first_try_accepted"] for r in acts),
        "rejected_share": ratio(counts["rejected"], counts["calls"]),
        "accepted_after_retry": sum(r["accepted_after_retry"] for r in acts),
        "fell_back_to_look": sum(r["fell_back_to_look"] for r in acts),
        "requests_per_turn": ratio(costs["requests"], len(records)),
        "rejection_reasons": {k: v for k, v in reasons.items() if v},
        "thought_parse_ok": parsed_thoughts,
        "thought_parse_failed": len(thoughts) - parsed_thoughts,
        "thought_error_reasons": dict(thought_errors),
        "thought_parse_rate": ratio(parsed_thoughts, len(thoughts)),
        "citations": sum(r["citations"] for r in thoughts),
        "valid_citations": sum(r["valid_citations"] for r in thoughts),
        "citation_validity": ratio(sum(r["valid_citations"] for r in thoughts),
                                   sum(r["citations"] for r in thoughts)),
        **costs,
        # Transport errors and action parse errors answer different questions.
        "errors": counts["errors"], "error_reasons": dict(errors),
    }


def run_picked(picked, client):
    """Score saved turns in their original context after verifying each source."""
    turns = picked["turns"]
    keys = [(str(t["db"]), t["tick"], t["npc"], t["kind"]) for t in turns]
    # Duplicate turns would count the same opportunity more than once.
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate picked turns")
    dbs = list(dict.fromkeys(k[0] for k in keys))
    # Check every source before the first paid request, including later source runs.
    checks = {db: check(db) for db in dbs}
    for db, result in checks.items():
        if not result["ok"]:
            raise ValueError(f"{db}: {result['difference']}")
    found = {}
    wanted = set(keys)
    for db in dbs:
        # Score before the saved reply so each candidate sees the original context.
        def visit(c, npc, kind, db=db):
            """Only spend requests on the turns selected for this screen."""
            key = (db, c.world.clock.tick, npc, kind)
            if key in wanted:
                found[key] = {"db": db, **score(c, npc, kind, client)}
        source, c = replay(db, visit)
        try:
            drift = difference(source, c)
            if drift:
                raise ValueError(f"{db}: {drift}")
        finally:
            c.world.log.db.close()
    # A stale selection must fail instead of silently producing a smaller screen.
    missing = wanted - found.keys()
    if missing:
        raise ValueError(f"picked turns not found: {sorted(missing)}")
    # Preserve selection order even though replay visits turns chronologically.
    records = [found[k] for k in keys]
    return {"seed": picked["seed"], "source_runs": dbs, "checks": checks,
            "records": records, "totals": totals(records)}
