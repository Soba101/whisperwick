#!/bin/zsh
# #126 bisect step: one commit, Victor benchmark, seed 2, 5 runs, 3 days. Screens "high (4-5 right) or low (0-2)"; 5 runs cannot separate 3/5 from 4/5.
# Compare: week 12 code 13/15 right, weeks 13-15 7/15 (see #126).
# Round-robin over the weeks keeps each represented if the batch is cut short.
# One run at a time: two runs on one llama-server are slower in total (#59).
# Usage: scripts/seed2-step-runs.sh DATA_DIR CHECKOUT TAG  (a worktree at the commit under test, with .env copied in)
# One run at a time (#59).
set -u
DATA=${1:?give the data directory}
DATA=${DATA:A}  # absolute: each run cd's into the checkout
CHECKOUT=${2:?give the checkout}
TAG=${3:?give a tag for the commit, used in file names}
DAYS=3
HERE=${0:A:h}

# One job per line: name week.
jobs=()
for rep in {1..5}; do
  for week in 1; do
    jobs+=("r${rep} $week")
  done
done

run_one() {
  # $1 name, $2 week
  local base="$DATA/bis-$TAG-$1"
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
    --days $DAYS --seed 2 --db "$base.db" > "$base.log" 2>&1)
  if reason=$(python3 -I "$HERE/run-complete.py" "$base.json" $DAYS); then
    echo "done $1 $(date +%H:%M)"
  else
    echo "INCOMPLETE $1 ($reason) $(date +%H:%M)"
  fi
}

for job in "${jobs[@]}"; do
  run_one ${=job}
done
echo "ALL DONE $(date)" > "$DATA/bis-$TAG-runs.done"
