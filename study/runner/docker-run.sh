#!/usr/bin/env bash
# Manual fallback: one run inside the study image with the proxy on the host. run.py --sandbox docker is the normal path.
# Usage: study/runner/docker-run.sh --task tasks/ib/<id> --body claude --sample 0 [--out runs]
# Paths are container paths: study/ is mounted at /study and is the working directory, so --task and --out are
# relative to study/ (tasks/ib/<id>, runs), not to the repository root; the archive lands under study/runs on the host.
# Start the proxy on the host first: study/.venv/bin/python study/runner/proxy.py
set -euo pipefail
STUDY="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${HS_PROXY_PORT:-8931}"
exec docker run --rm --add-host=host.docker.internal:host-gateway \
  -e HS_PROXY_PORT="$PORT" -e HS_SIMPLE_PROMPT="${HS_SIMPLE_PROMPT:-1}" -e HS_TOOL_SEARCH="${HS_TOOL_SEARCH:-false}" \
  -v "$STUDY:/study" --tmpfs /hswork:rw,size=2g -e HS_WORK_ROOT=/hswork -w /study --user "$(id -u):$(id -g)" -e HOME=/tmp/hshome \
  harness-study python3 runner/run.py --sandbox host --proxy "http://host.docker.internal:$PORT" "$@"
