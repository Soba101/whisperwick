#!/bin/zsh
# Week 6 runs (docs/week6-plan.md section 4), several at once.
# llama-server on the PC has 4 slots, so 4 runs share the GPU at a time.
# Usage: scripts/week6-runs.sh DATA_DIR [JOBS_AT_ONCE]
# Run it from a separate checkout (a git worktree): runs load the code they start with,
# so the main checkout stays free for work. DATA_DIR should be the main repo's data/.
set -u
DATA=${1:?give the data directory}
AT_ONCE=${2:-4}
DAYS=3

# One job per line: name seed player-script memory(on|off).
# Main grid: 5 seeds x 3 scripts, villager memory on.
# Baseline: 3 seeds x none, villager memory off (week 5 prompts), same seeds.
# Ordered by seed, each seed's baseline right after it, so a batch cut short still has
# whole seeds and a memory on/off pair to compare.
jobs=()
for seed in 1 2 3 4 5; do
  for s in none blame_hal accuse_victor; do
    jobs+=("s${seed}-${s} $seed $s on")
  done
  if (( seed <= 3 )); then
    jobs+=("s${seed}-none-off $seed none off")
  fi
done

run_one() {
  # $1 name, $2 seed, $3 script, $4 memory
  local db="$DATA/w6-$1.db"
  # A finished run has its sidecar: skip it, so the batch can be restarted safely.
  if [[ -f "$DATA/w6-$1.json" ]]; then
    echo "skip $1 (done)"
    return
  fi
  rm -f "$db" "$DATA/w6-$1.beliefs.jsonl" "$DATA/w6-$1.agent.jsonl"
  WHISPERWICK_MEMORY=$4 uv run whisperwick play --script "players/$3.yaml" \
    --days $DAYS --seed $2 --db "$db" > "$DATA/w6-$1.log" 2>&1
  echo "done $1 $(date +%H:%M)"
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
echo "ALL DONE $(date)" > "$DATA/w6-runs.done"
