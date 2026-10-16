#!/bin/zsh
# Week 10 player runs (docs/week10-plan.md section 1), seeds 1-5, memory on.
# Four scripts per seed: none, accuse_victor, blame_hal, hide_knife. Its none run is the second one
# of each seed (w8-base-s1..5 is the first), to see how much a seed varies with no player.
# Villagers answer at temperature 0.7: the same seed is not the same game.
# Ordered by seed so a batch cut short still has whole seeds.
# Since week 9, 4 at once is fine on llama-server.
# Never run this batch while the user plays the web demo.
# Usage: scripts/week10-player-runs.sh DATA_DIR [AT_ONCE]
# Run from a git worktree of main. Runs use the checkout this script lives in.
set -u
DATA=${1:?give the data directory}
AT_ONCE=${2:-4}
DAYS=3
HERE=${0:A:h}

# Keep relative data paths tied to where the batch was started.
DATA=${DATA:A}
cd "$HERE/.." || exit 1
# A zero or invalid limit would leave the queue waiting forever.
if [[ "$AT_ONCE" != <-> ]] || (( AT_ONCE < 1 )); then
  echo "AT_ONCE must be a positive integer" >&2
  exit 1
fi

# One job per line: name seed player-script.
jobs=()
for seed in 1 2 3 4 5; do
  for s in none accuse_victor blame_hal hide_knife; do
    jobs+=("s${seed}-${s} $seed $s")
  done
done

run_one() {
  # $1 name, $2 seed, $3 script
  local base="$DATA/w10-$1"
  local reason
  # Skip only accepted runs, so the batch can be restarted.
  if python3 -I "$HERE/run-complete.py" "$base.json" $DAYS > /dev/null; then
    echo "skip $1 (done)"
    return
  fi
  # Keep the old files of an incomplete run instead of deleting them.
  local stamp=$(date +%Y%m%d-%H%M%S)
  for ext in db json beliefs.jsonl agent.jsonl log; do
    [[ -e "$base.$ext" ]] && mv "$base.$ext" "$base.$ext.incomplete-$stamp"
  done
  "$HERE/wait-server.sh"  # never start a run on a dead server
  WHISPERWICK_MEMORY=on uv run whisperwick play --script "players/$3.yaml" \
    --days $DAYS --seed $2 --db "$base.db" > "$base.log" 2>&1
  # A sidecar alone does not prove that all three days finished.
  if reason=$(python3 -I "$HERE/run-complete.py" "$base.json" $DAYS); then
    echo "done $1 $(date +%H:%M)"
  else
    echo "INCOMPLETE $1 ($reason) $(date +%H:%M)"
  fi
}

# Start up to AT_ONCE runs, then wait for a slot before starting the next.
# Keep our own process ids: $(jobs -r) sees no jobs in its subshell.
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
# Let the last runs finish before marking the batch as ended.
wait
echo "ALL DONE $(date)" > "$DATA/w10-runs.done"
