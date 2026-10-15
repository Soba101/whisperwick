#!/bin/zsh
# Week 8 check of the "What you knew before today:" heading (#56), seeds 6-10, memory on.
# Each seed runs twice, one at a time: with the heading (current code) and without it
# (the week 7 code, 78daf17). The only prompt difference between the two is the heading.
# Heading first, then no heading, per seed, so a batch cut short still has whole pairs.
# One run at a time: two runs on one llama-server are slower in total (#59).
# Usage: scripts/week8-heading-runs.sh DATA_DIR HEADING_CHECKOUT NO_HEADING_CHECKOUT
# Both checkouts are git worktrees: runs load the code they start with.
set -u
DATA=${1:?give the data directory}
WITH=${2:?give the checkout with the heading}
WITHOUT=${3:?give the checkout without the heading (78daf17)}
DAYS=3
HERE=${0:A:h}

# One job per line: name seed checkout.
jobs=()
for seed in 6 7 8 9 10; do
  jobs+=("s${seed}-head $seed $WITH")
  jobs+=("s${seed}-nohead $seed $WITHOUT")
done

run_one() {
  # $1 name, $2 seed, $3 checkout
  local base="$DATA/w8h-$1"
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
echo "ALL DONE $(date)" > "$DATA/w8h-runs.done"
