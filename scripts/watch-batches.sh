#!/bin/zsh
# Batch heartbeat: watch-server.sh only checks the model server is up. On 2026-10-22 a whole
# batch failed in its first second (the new worktree had no .env) and nobody saw it for 8 hours.
# This checks every minute for a run marked INCOMPLETE in any batch log, logs it and notifies.
# Usage: scripts/watch-batches.sh [LOG]   (run it in the background with nohup, from the repo)
LOG=${1:-data/batch-watch.log}
typeset -A seen  # batch log -> INCOMPLETE lines already reported
first=1          # the first pass only records old failures, so they are not reported again
while true; do
  # (N): a pattern that matches nothing is simply empty, not a zsh error.
  for f in data/*batch.log(N) data/*/batch.log(N); do
    n=$(grep -c INCOMPLETE "$f")
    if (( !first && n > ${seen[$f]:-0} )); then
      line=$(grep INCOMPLETE "$f" | tail -1)
      echo "$(date '+%Y-%m-%d %H:%M:%S') $f: $line ($n incomplete)" >> "$LOG"
      osascript -e "display notification \"$line\" with title \"Whisperwick batch: run failed\""
    fi
    seen[$f]=$n
  done
  first=0
  sleep 60
done
