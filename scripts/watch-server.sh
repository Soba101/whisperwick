#!/bin/zsh
# Heartbeat for the model server on the PC: checks every minute, logs each up/down change
# and shows a macOS notification.
# 2026-10-16: it also restarts llama-server when it stays down. Closing its window on the PC
# stopped it at 02:43 and the scheduled task did not bring it back (a closed window is not a failure).
# Usage: scripts/watch-server.sh [URL] [LOG]   (run it in the background with nohup)
URL=${1:-http://100.75.187.23:8080/health}
LOG=${2:-data/server-watch.log}
# Kev uses the same GPU. While its task runs (even while it is still loading), llama-server is
# down on purpose: a judging swap. So we ask the PC, not Kev's port.
KEV_STATE='powershell -NoProfile -Command "(Get-ScheduledTask -TaskName \"Whisperwick Kev\").State"'
# The PC's SSH login (user@host) comes from WHISPERWICK_PC_SSH, in the environment or the git-ignored .env,
# so no personal name is kept in the repository.
PC=${WHISPERWICK_PC_SSH:-$(grep -m1 '^WHISPERWICK_PC_SSH=' .env 2>/dev/null | cut -d= -f2)}
[[ -n $PC ]] || { echo "set WHISPERWICK_PC_SSH=user@host in .env" >&2; exit 1; }
# %USERPROFILE% is expanded on the PC, so the Windows user name is not written here either.
START='powershell -NoProfile -ExecutionPolicy Bypass -File %USERPROFILE%\whisperwick-servers\start-llama.ps1'
# While this file exists the heartbeat only watches: another model is being tested on the
# same port, and restarting the usual one would put two models on the GPU.
PAUSE=data/server-watch.pause
state=unknown
down_for=0      # minutes in a row the server has been down
last_restart=0  # epoch seconds of our last restart, so we try at most once per 15 minutes
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
  if [[ $now == up ]]; then
    down_for=0
  else
    (( down_for++ ))
    # Down for 3 minutes and no restart in the last 15 minutes: ask whether Kev is running.
    if [[ -e $PAUSE ]]; then
      kev=paused
    elif (( down_for >= 3 )) && (( $(date +%s) - last_restart > 900 )); then
      kev=$(ssh -o ConnectTimeout=10 -o BatchMode=yes $PC "$KEV_STATE" 2>/dev/null | tr -d '\r')
    else
      kev=skip
    fi
    # Restart only when the PC answered and Kev's task is not running.
    if [[ $kev == Ready ]]; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') restarting llama-server" >> "$LOG"
      last_restart=$(date +%s)
      ssh -o ConnectTimeout=10 -o BatchMode=yes $PC "$START" > /dev/null 2>&1
      echo "$(date '+%Y-%m-%d %H:%M:%S') restart script ended (exit $?)" >> "$LOG"
    fi
  fi
  sleep 60
done
