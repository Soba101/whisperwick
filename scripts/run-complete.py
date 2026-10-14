# Is this run finished? Usage: run-complete.py SIDECAR DAYS
# Exit 0 only if the sidecar exists, parses, did not stop early, and played every planned minute.
# A stopped or short run still writes a sidecar, so the sidecar alone proves nothing.
import json
import sys


def why_incomplete(path, days):
    try:
        side = json.load(open(path))
    except FileNotFoundError:
        return "no sidecar"
    except ValueError:
        return "sidecar is not valid JSON"
    if not isinstance(side, dict):
        return "sidecar is not a JSON object"
    stats = side.get("stats")
    if isinstance(stats, dict) and stats.get("stopped"):
        return f"stopped early ({stats['stopped']})"
    minutes = side.get("minutes")
    if not isinstance(minutes, (int, float)) or minutes < days * 1440:
        return f"played {minutes} of {days * 1440} minutes"
    return None


if __name__ == "__main__":
    reason = why_incomplete(sys.argv[1], int(sys.argv[2]))
    if reason:
        print(reason)
        sys.exit(1)
