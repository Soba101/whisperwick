#!/bin/zsh
# Heartbeat for the model server on the PC: checks every minute, logs each up/down change
# and shows a macOS notification. It only watches; restarting is done on the PC.
# Usage: scripts/watch-server.sh [URL] [LOG]   (run it in the background with nohup)
URL=${1:-http://100.75.187.23:8080/health}
LOG=${2:-data/server-watch.log}
state=unknown
while true; do
  # --noproxy: this Mac's system proxy slows or blocks Tailscale addresses.
  code=$(curl --noproxy '*' -s -m 10 -o /dev/null -w "%{http_code}" "$URL")
  now=$([[ $code == 200 ]] && echo up || echo down)
  if [[ $now != $state ]]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') $now (HTTP $code)" >> "$LOG"
    # Only notify on a real change, not on the first check.
    [[ $state != unknown ]] && osascript -e "display notification \"model server is $now\" with title \"Whisperwick\""
    state=$now
  fi
  sleep 60
done
