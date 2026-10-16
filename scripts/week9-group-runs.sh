#!/bin/zsh
# Week 9 five-checks test of group turns (docs/week9-plan.md, section 2), memory on, 3 days.
# Runs one at a time: two runs on one llama-server are slower in total (#59).
# Usage: scripts/week9-group-runs.sh DATA_DIR CHECKOUT on|off SCRIPT SEED...
#   e.g. scripts/week9-group-runs.sh data ../whisperwick-w9 on none 1 2 3 4 5
# CHECKOUT is a git worktree: a run loads the code it starts with, so main can change meanwhile.
# Run names: w9g-s<seed>-<script>-<on|off>. Restartable: finished runs are skipped.
set -u
DATA=${1:?give the data directory}
CODE=${2:?give the checkout to run from}
GROUP=${3:?give on or off}
SCRIPT=${4:?give the player script name, e.g. none}
shift 4
DAYS=3
HERE=${0:A:h}

run_one() {
  # $1 seed
  local base="$DATA/w9g-s$1-$SCRIPT-$GROUP"
  local reason
  # Skip only runs that run-complete.py accepts, so the batch can be restarted.
  if python3 -I "$HERE/run-complete.py" "$base.json" $DAYS > /dev/null; then
    echo "skip s$1 (done)"
    return
  fi
  # Keep the old files of an incomplete run under a new name instead of deleting them.
  local stamp=$(date +%Y%m%d-%H%M%S)
  for ext in db json beliefs.jsonl agent.jsonl log; do
    [[ -e "$base.$ext" ]] && mv "$base.$ext" "$base.$ext.incomplete-$stamp"
  done
  "$HERE/wait-server.sh"  # never start a run on a dead server
  # The switch is set per run, so on and off runs can share one checkout.
  (cd "$CODE" && WHISPERWICK_MEMORY=on WHISPERWICK_GROUP_TURNS=$GROUP uv run whisperwick play \
    --script "players/$SCRIPT.yaml" --days $DAYS --seed $1 --db "$base.db" > "$base.log" 2>&1)
  if reason=$(python3 -I "$HERE/run-complete.py" "$base.json" $DAYS); then
    echo "done s$1 $(date +%H:%M)"
  else
    echo "INCOMPLETE s$1 ($reason) $(date +%H:%M)"
  fi
}

for seed in "$@"; do
  run_one $seed
done
echo "ALL DONE $(date)" > "$DATA/w9g-$SCRIPT-$GROUP.done"
