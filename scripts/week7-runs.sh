#!/bin/zsh
# Week 7 control runs (docs/week7-plan.md section 4): the `none` script only,
# seeds 1 2 3 4 5 42, each with villager memory on, then off.
# One run at a time: the week 7 batch showed two runs sharing one llama-server
# are slower in total (~4.2 s per call vs 1.7 s alone). Prompt reading does not overlap.
# See issue #59.
# Usage: scripts/week7-runs.sh DATA_DIR [JOBS_AT_ONCE]
# Run it from a separate checkout (a git worktree): runs load the code they start with,
# so the main checkout stays free for work. DATA_DIR should be the main repo's data/.
set -u
DATA=${1:?give the data directory}
AT_ONCE=${2:-1}
DAYS=3
HERE=${0:A:h}

# One job per line: name seed player-script memory(on|off).
# Ordered by seed, memory on then off, so a batch cut short still has whole on/off pairs.
jobs=()
for seed in 1 2 3 4 5 42; do
  jobs+=("s${seed}-none $seed none on")
  jobs+=("s${seed}-none-off $seed none off")
done

run_one() {
  # $1 name, $2 seed, $3 script, $4 memory
  local base="$DATA/w7-$1"
  local reason
  # A sidecar alone is not enough: a run that stopped early or played too few minutes
  # also writes one. Skip only runs that run-complete.py accepts.
  if python3 -I "$HERE/run-complete.py" "$base.json" $DAYS > /dev/null; then
    echo "skip $1 (done)"
    return
  fi
  # Keep the old files of an incomplete run under a new name instead of deleting them.
  local stamp=$(date +%Y%m%d-%H%M%S)
  for ext in db json beliefs.jsonl agent.jsonl log; do
    [[ -e "$base.$ext" ]] && mv "$base.$ext" "$base.$ext.incomplete-$stamp"
  done
  WHISPERWICK_MEMORY=$4 uv run whisperwick play --script "players/$3.yaml" \
    --days $DAYS --seed $2 --db "$base.db" > "$base.log" 2>&1
  if reason=$(python3 -I "$HERE/run-complete.py" "$base.json" $DAYS); then
    echo "done $1 $(date +%H:%M)"
  else
    echo "INCOMPLETE $1 ($reason) $(date +%H:%M)"
  fi
}

# Simple queue: start up to AT_ONCE runs, wait for any to end, start the next.
# We keep our own list of process ids: `$(jobs -r)` runs in a subshell, which sees no
# jobs, so a first version of this script started all 18 runs at once.
running=()
for job in "${jobs[@]}"; do
  while true; do
    alive=()
    for pid in "${running[@]}"; do
      kill -0 $pid 2>/dev/null && alive+=($pid)
    done
    running=("${alive[@]}")
    (( ${#running[@]} < AT_ONCE )) && break
    sleep 15
  done
  run_one ${=job} &
  running+=($!)
  sleep 2  # stagger starts a little
done
wait
echo "ALL DONE $(date)" > "$DATA/w7-runs.done"
