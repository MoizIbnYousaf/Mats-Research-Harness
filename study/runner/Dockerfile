# Study image for the four routable bodies (PLAN v3 line 35): node 22 for the CLIs, python + pytest for the reruns.
# No Ori: run.py launches each CLI directly with the proxy env from harness_env.py. Antigravity runs on the host.
FROM node:22-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip git curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages pytest
# Pinned CLI versions (the versions the manifest audit expects); npm served these on 2026-09-02. Bump all four together
# and re-date: a cached rebuild keeps the old layer, an unpinned --no-cache rebuild would pull whatever npm serves that day.
RUN npm i -g @anthropic-ai/claude-code@2.1.258 @openai/codex@0.152.1 opencode-ai@1.18.26 @earendil-works/pi-coding-agent@0.84.4
# CLI versions at build time, on disk for the manifest audit
RUN { claude --version; codex --version; opencode --version; pi --version; } 2>&1 | tee /versions.txt
WORKDIR /study
