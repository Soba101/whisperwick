#!/bin/zsh
# Wait until the model server answers /health, so a batch never starts a run on a dead server.
# (2026-10-16: a run started while llama-server was down stops after a few errors and is wasted.)
# Usage: scripts/wait-server.sh [URL]   Prints one line when it has to wait.
# WAIT_LIMIT_MIN (default 60): give up after this many minutes and exit 1.
# (2026-11-12: a server that never started kept a batch waiting 8 h with no alert, #129.)
# Callers ignore the exit code on purpose: the next run then fails fast, is marked
# INCOMPLETE, and watch-batches.sh reports it.
URL=${1:-http://100.75.187.23:8080/health}
LIMIT=${WAIT_LIMIT_MIN:-60}
LOG=${0:A:h:h}/data/batch-watch.log
waited=0
alerted=0
# --noproxy: this Mac's system proxy slows or blocks Tailscale addresses.
until [[ $(curl --noproxy '*' -s -m 10 -o /dev/null -w "%{http_code}" "$URL") == 200 ]]; do
  (( waited == 0 )) && echo "server down, waiting $(date +%H:%M)"
  # Alert once after 10 min: the heartbeat restarts the server within ~3 min when it is not paused.
  if (( waited >= 10 && ! alerted )); then
    echo "$(date '+%F %T') server down for 10 min during a batch: $URL" >> "$LOG"
    osascript -e "display notification \"server down 10 min during a batch\" with title \"Whisperwick batch\""
    alerted=1
  fi
  if (( waited >= LIMIT )); then
    echo "server still down after $LIMIT min, giving up $(date +%H:%M)"
    echo "$(date '+%F %T') gave up waiting after $LIMIT min: $URL" >> "$LOG"
    exit 1
  fi
  (( waited += 1 ))
  sleep 60
done
(( waited )) && echo "server back $(date +%H:%M)"
exit 0
