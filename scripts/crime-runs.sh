#!/bin/zsh
# #109: generated crimes 1-10 (week 14 generator), one run each, no role, memory on, 3 days.
# Reported against the Victor benchmark (#90), not judged: a generated crime is a different test.
# Fixed crime numbers, so the same batch can be rerun on later code.
# One run at a time: two runs on one llama-server are slower in total (#59).
# Usage: scripts/crime-runs.sh DATA_DIR CHECKOUT
# The checkout is a git worktree at main: runs load the code they start with.
set -u
DATA=${1:?give the data directory}
DATA=${DATA:A}  # absolute: each run cd's into the checkout
CHECKOUT=${2:?give the checkout at main}
DAYS=3
HERE=${0:A:h}

# One job per line: name crime number.
jobs=()
for crime in {1..10}; do
  jobs+=("c${crime} $crime")
done

run_one() {
  # $1 name, $2 crime number
  local base="$DATA/w15c-$1"
  local reason
  # Skip only runs that run-complete.py accepts, so the batch can be restarted.
  if python3 -I "$HERE/run-complete.py" "$base.json" $DAYS > /dev/null; then
    echo "skip $1 (done)"
    return
  fi
  # Keep the old files of an incomplete run under a new name instead of deleting them.
  local stamp=$(date +%Y%m%d-%H%M%S)
  for ext in db json beliefs.jsonl agent.jsonl log; do
    [[ -e "$base.$ext" ]] && mv "$base.$ext" "$base.$ext.incomplete-$stamp"
  done
  "$HERE/wait-server.sh"  # never start a run on a dead server
  (cd "$CHECKOUT" && WHISPERWICK_MEMORY=on uv run whisperwick play --script players/none.yaml \
    --days $DAYS --crime $2 --db "$base.db" > "$base.log" 2>&1)
  if reason=$(python3 -I "$HERE/run-complete.py" "$base.json" $DAYS); then
    echo "done $1 $(date +%H:%M)"
  else
    echo "INCOMPLETE $1 ($reason) $(date +%H:%M)"
  fi
}

for job in "${jobs[@]}"; do
  run_one ${=job}
done
echo "ALL DONE $(date)" > "$DATA/w15c-runs.done"
