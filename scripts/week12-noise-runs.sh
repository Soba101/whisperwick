#!/bin/zsh
# Week 12 option A: same-seed noise, seeds 1-2, 10 runs each, memory on, 3 days.
# Current code, recall ranking off, using players/none.yaml.
# Repeats use the same seed; only model sampling differs.
# Round-robin order keeps both seeds represented if the batch is cut short.
# One run at a time: two runs on one llama-server are slower in total (#59).
# Usage: scripts/week12-noise-runs.sh DATA_DIR CHECKOUT
# The checkout is a git worktree at main: runs load the code they start with.
set -u
DATA=${1:?give the data directory}
CHECKOUT=${2:?give the checkout at main}
DAYS=3
HERE=${0:A:h}

# One job per line: name seed checkout.
jobs=()
for rep in {1..10}; do
  for seed in 1 2; do
    jobs+=("s${seed}-r${rep} $seed $CHECKOUT")
  done
done

run_one() {
  # $1 name, $2 seed, $3 checkout
  local base="$DATA/w12n-$1"
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
  (cd "$3" && WHISPERWICK_MEMORY=on uv run whisperwick play --script players/none.yaml \
    --days $DAYS --seed $2 --db "$base.db" > "$base.log" 2>&1)
  if reason=$(python3 -I "$HERE/run-complete.py" "$base.json" $DAYS); then
    echo "done $1 $(date +%H:%M)"
  else
    echo "INCOMPLETE $1 ($reason) $(date +%H:%M)"
  fi
}

for job in "${jobs[@]}"; do
  run_one ${=job}
done
echo "ALL DONE $(date)" > "$DATA/w12n-runs.done"
