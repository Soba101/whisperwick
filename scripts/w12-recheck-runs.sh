#!/bin/zsh
# #126 check: the week 12 code (870823d) again, Victor benchmark, seed 2, 5 runs, 3 days. Was the 9/10 baseline luck or drift?
# Compare: w12n seed 2 (9/10 right) and the s2h hunt (weeks 13-15: 7/15).
# Round-robin over the weeks keeps each represented if the batch is cut short.
# One run at a time: two runs on one llama-server are slower in total (#59).
# Usage: scripts/w12-recheck-runs.sh DATA_DIR CHECKOUT  (a worktree at 870823d with .env copied in)
# One run at a time (#59).
set -u
DATA=${1:?give the data directory}
DATA=${DATA:A}  # absolute: each run cd's into the checkout
CHECKOUT=${2:?give the checkout}
DAYS=3
HERE=${0:A:h}

# One job per line: name week.
jobs=()
for rep in {1..5}; do
  for week in 12; do
    jobs+=("w${week}-r${rep} $week")
  done
done

run_one() {
  # $1 name, $2 week
  local base="$DATA/w12k-$1"
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
echo "ALL DONE $(date)" > "$DATA/w12k-runs.done"
