#!/bin/zsh
# #126 hunt: the Victor benchmark, seed 2 only, 5 runs at the end of weeks 13, 14 and 15, 3 days.
# Baseline: the week 12 noise runs (w12n, seed 2 right 9/10) and w16c (1/5). Finds the week that broke seed 2.
# Round-robin over the weeks keeps each represented if the batch is cut short.
# One run at a time: two runs on one llama-server are slower in total (#59).
# Usage: scripts/seed2-hunt-runs.sh DATA_DIR CHECKOUT_PREFIX  (checkouts PREFIX-w13, -w14, -w15)
# Each checkout is a git worktree at that week's last commit, with .env copied in.
set -u
DATA=${1:?give the data directory}
DATA=${DATA:A}  # absolute: each run cd's into the checkout
PREFIX=${2:?give the checkout prefix}
DAYS=3
HERE=${0:A:h}

# One job per line: name week.
jobs=()
for rep in {1..5}; do
  for week in 13 14 15; do
    jobs+=("w${week}-r${rep} $week")
  done
done

run_one() {
  # $1 name, $2 week
  local base="$DATA/s2h-$1"
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
  (cd "$PREFIX-w$2" && WHISPERWICK_MEMORY=on uv run whisperwick play --script players/none.yaml \
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
echo "ALL DONE $(date)" > "$DATA/s2h-runs.done"
