#!/bin/zsh
# Week 12 option B: the goods scenario (place-specific items), seeds 1-2, 10 runs each,
# memory on, 3 days. Same setup as week12-noise-runs.sh so the two batches compare directly.
# Recall ranking off, players/none.yaml, scenarios/murder_of_the_mayor_goods.yaml.
# Repeats use the same seed; only model sampling differs.
# Round-robin order keeps both seeds represented if the batch is cut short.
# One run at a time: two runs on one llama-server are slower in total (#59).
# Usage: scripts/week12-goods-runs.sh DATA_DIR CHECKOUT
# The checkout is a git worktree with the goods scenario: runs load the code they start with.
set -u
DATA=${1:?give the data directory}
DATA=${DATA:A}  # absolute: each run cd's into the checkout
CHECKOUT=${2:?give the checkout with the goods scenario}
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
  local base="$DATA/w12g-$1"
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
    --scenario scenarios/murder_of_the_mayor_goods.yaml \
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
echo "ALL DONE $(date)" > "$DATA/w12g-runs.done"
