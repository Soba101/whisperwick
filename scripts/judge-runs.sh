#!/bin/zsh
# Judge every finished run with Kev, one after another (Kev has the GPU to itself).
# Usage: scripts/judge-runs.sh [PREFIX] [DAYS]   e.g. scripts/judge-runs.sh w6-   (default: every run)
# Restartable: a run that already has its .judge.json is skipped.
# DAYS (default 3) is the planned length: a run that stopped early or played fewer days is skipped.
# Kev and qwen do not fit on the GPU together, so stop llama-server and start Kev first.
set -u
cd "$(dirname "$0")/.."
PREFIX=${1:-}
DAYS=${2:-3}

# Kev's address and key come from .env (the key is never printed).
KEV_URL=$(grep '^KEV_URL=' .env | cut -d= -f2-)
KEV_KEY=$(grep '^KEV_API_KEY=' .env | cut -d= -f2-)

kev_ready() {
  # Kev answers status even when stuck, so look at its queue too: requests left over from
  # a client that gave up stalled the whole judging once. Queue must be empty to start.
  # --noproxy: this Mac has a system proxy that slows or blocks local addresses.
  curl --noproxy '*' -s -m 10 -H "Authorization: Bearer $KEV_KEY" "$KEV_URL/v1/models" |
    python3 -c "import json,sys; m=json.load(sys.stdin)['models'][0]; sys.exit(m['batches']['queued'] != 0)" 2>/dev/null
}

for sidecar in data/${PREFIX}*.json(N); do
  # Only run sidecars: skip judge files and the like.
  [[ $sidecar == *.judge.json ]] && continue
  db=${sidecar%.json}.db
  [[ -f $db ]] || continue
  if [[ -f ${sidecar%.json}.judge.json ]]; then
    echo "skip $db (already judged)"
    continue
  fi
  # A stopped or short run still has a sidecar, but must be rerun, never judged.
  if reason=$(python3 -I scripts/run-complete.py "$sidecar" $DAYS); then :; else
    echo "skip $db (incomplete: $reason)"
    continue
  fi
  if ! kev_ready; then
    echo "STOP: Kev not reachable at $KEV_URL, or its queue is not empty. Restart Kev, then run this again."
    exit 1
  fi
  if uv run whisperwick judge "$db" --limit 40 > /dev/null 2>&1; then
    echo "judged $db $(date +%H:%M)"
  else
    echo "FAILED $db"
  fi
done
echo "ALL JUDGED"
