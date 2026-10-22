#!/bin/zsh
# Batch heartbeat: watch-server.sh only checks the model server is up. On 2026-10-22 a whole
# batch failed in its first second (the new worktree had no .env) and nobody saw it for 8 hours.
# This checks every minute for a run marked INCOMPLETE in any batch log, and for a batch whose
# runs stopped making progress; it logs each and notifies.
# Usage: scripts/watch-batches.sh [LOG]   (run it in the background with nohup, from the repo)
LOG=${1:-data/batch-watch.log}
typeset -A seen  # batch log -> INCOMPLETE lines already reported
first=1          # the first pass only records old failures, so they are not reported again
stalled=0        # report a stall once, not every minute
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
  # Stall check: while a batch script runs, the newest run log must grow every 15 minutes
  # (a run prints a line per game hour). Silence means a hung run or no run at all.
  if pgrep -f '[s]cripts/.*-runs\.sh' > /dev/null; then
    newest=(data/**/w[0-9]*.log(N.om[1]))  # run logs only, not the demo web-play.log
    age=$(( $(date +%s) - $(stat -f %m "$newest" 2>/dev/null || echo 0) ))
    if (( age > 900 )); then
      if (( !stalled )); then
        echo "$(date '+%Y-%m-%d %H:%M:%S') stalled: $newest silent for $(( age / 60 )) min" >> "$LOG"
        osascript -e "display notification \"no run progress for $(( age / 60 )) min\" with title \"Whisperwick batch: stalled\""
      fi
      stalled=1
    else
      stalled=0
    fi
  fi
  sleep 60
done
