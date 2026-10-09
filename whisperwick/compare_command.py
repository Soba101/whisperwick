"""The body of `whisperwick compare`, kept out of cli.py to keep that file small."""

from pathlib import Path

from whisperwick import compare


def compare_runs(dbs: list[Path]) -> str:
    """Load every run and format the report. Raises FileNotFoundError for a missing db."""
    for db in dbs:
        if not db.is_file():
            raise FileNotFoundError(f"No such file: {db}")
    runs = [compare.load_run(db) for db in dbs]
    return compare.format_compare(runs, compare.load_names(runs))
