#!/bin/zsh
# Week 14 E1 (#104): a higher sampling temperature, no role, seeds 1-2, 5 runs each, memory on, 3 days.
# Baseline: the week 12 noise runs (data/w12n-*) at the usual 0.7, same villager code with no role.
# Repeats use the same seed; only model sampling differs.
# Round-robin order keeps every role and seed represented if the batch is cut short.
# One run at a time: two runs on one llama-server are slower in total (#59).
# Usage: scripts/week14-temp-runs.sh DATA_DIR CHECKOUT [TEMPERATURE]  (default 1.0)
# The checkout is a git worktree at main: runs load the code they start with.
set -u
DATA=${1:?give the data directory}
DATA=${DATA:A}  # absolute: each run cd's into the checkout
CHECKOUT=${2:?give the checkout at main}
DAYS=3
TEMP=${3:-1.0}
HERE=${0:A:h}

# One job per line: name seed.
jobs=()
for rep in {1..5}; do
  for seed in 1 2; do
    jobs+=("t${TEMP}-s${seed}-r${rep} $seed")
  done
done

run_one() {
  # $1 name, $2 seed
  local base="$DATA/w14t-$1"
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
  (cd "$CHECKOUT" && WHISPERWICK_MEMORY=on LLM_TEMPERATURE=$TEMP uv run whisperwick play --script players/none.yaml \
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
echo "ALL DONE $(date)" > "$DATA/w14t-runs.done"
