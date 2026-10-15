#!/bin/zsh
# Wait until the model server answers /health, so a batch never starts a run on a dead server.
# (2026-10-16: a run started while llama-server was down stops after a few errors and is wasted.)
# Usage: scripts/wait-server.sh [URL]   Prints one line when it has to wait.
URL=${1:-http://100.75.187.23:8080/health}
waited=0
# --noproxy: this Mac's system proxy slows or blocks Tailscale addresses.
until [[ $(curl --noproxy '*' -s -m 10 -o /dev/null -w "%{http_code}" "$URL") == 200 ]]; do
  (( waited == 0 )) && echo "server down, waiting $(date +%H:%M)"
  waited=1
  sleep 60
done
(( waited )) && echo "server back $(date +%H:%M)"
exit 0
