"""The body of `whisperwick eval`, kept out of cli.py. Code only, no model."""

from pathlib import Path

from whisperwick import compare, eval_format, eval_measures, eval_summary


def eval_runs(dbs: list[Path]) -> str:
    """Raises FileNotFoundError for a missing db. Returns the whole report as text."""
    for db in dbs:
        if not db.is_file():
            raise FileNotFoundError(f"No such file: {db}")
    runs = [compare.load_run(db) for db in dbs]
    names = compare.load_names(runs)
    ms = [eval_measures.measure(r, db) for r, db in zip(runs, dbs, strict=True)]
    out = [
        "Runs (held at the end, judged against the scenario secret):",
        *eval_format.run_rows(ms, names),
        "",
        "Measures (Talk = share of villager events; Sourced = suspect thoughts with a valid "
        "citation; Aims n/d/x = new/done/dropped; Stalls = awake game hours with no "
        "villager event):",
        *eval_format.measure_rows(ms),
    ]
    judged = eval_format.judge_rows(ms)
    if judged:
        out += ["", "Judge (from <db>.judge.json):", *judged]
    out += ["", "Summary", "Divergence:", *eval_summary.divergence(ms)]
    out += ["", "Memory on versus off (averages):", *eval_summary.memory_rows(ms)]
    return "\n".join(out)
