#!/bin/zsh
# Show how far each live run has got, and what the world has recorded so far.
#
# Usage:
#   scripts/run-status.sh            # all runs whose names start with "w5-"
#   scripts/run-status.sh w6-        # another batch
#   scripts/run-status.sh --watch    # refresh every 30 seconds (Ctrl+C to stop)
#
# It only READS files in data/: the run logs and the event databases.
# It never touches a run, so it is safe to use while runs are going.

cd "$(dirname "$0")/.." || exit 1

# --watch: clear the screen and redraw every 30 seconds.
if [[ "$1" == "--watch" ]]; then
  shift
  while true; do clear; "$0" "$@"; sleep 30; done
fi

prefix="${1:-w5-}"
DAYS=3  # runs are 3 game days, from day 1 08:00 to day 4 08:00

# Say so plainly when there is nothing to show, instead of printing nothing.
# (Runs and their logs only exist on the machine that ran them: the Mac.)
if ! ls data/${prefix}*.log >/dev/null 2>&1; then
  echo "No run logs matching data/${prefix}*.log in $(pwd)."
  echo "Runs live on the Mac in ~/DocumentsMac/Codes/whisperwick/data/."
  exit 0
fi
for log in data/${prefix}*.log; do
  name=$(basename "$log" .log)
  db="data/$name.db"
  # The run prints "Sidecar: ..." at the very end, so that line means it finished.
  if grep -q "^Sidecar:" "$log"; then
    state="done"
  else
    # Last progress line looks like: "day 2 17:00  calls 439  rejected 14  errors 0 ..."
    last=$(grep "^day " "$log" | tail -1)
    day=$(echo "$last" | awk '{print $2}')
    hour=$(echo "$last" | awk '{print substr($3,1,2)+0}')
    # Game hours since the start (day 1 08:00), as a share of the whole run.
    if [[ -n "$day" ]]; then
      pct=$(( ((day - 1) * 24 + hour - 8) * 100 / (DAYS * 24) ))
      state="running ${pct}%  ($last)"
    else
      state="starting"
    fi
  fi
  # Errors in a row stop a run; show the error count so a dead model server is easy to spot.
  echo "== $name: $state"
  # World facts so far: every arrest and release, straight from the event log.
  if [[ -f "$db" ]]; then
    sqlite3 "$db" "select '   ' || type || ': ' || actor || ' -> ' || json_extract(data,'$.target') \
      || '  (day ' || (tick / 1440 + 1) || ' ' || printf('%02d:%02d', tick % 1440 / 60, tick % 60) || ')' \
      from events where type in ('arrest','release') order by id" 2>/dev/null
  fi
done

# The batch script writes this file when every run in it has finished.
# (A tick is one game minute from day 1 00:00, which is how the times above are worked out.)
[[ -f data/${prefix}runs.done ]] && echo "All runs in the batch are finished."
