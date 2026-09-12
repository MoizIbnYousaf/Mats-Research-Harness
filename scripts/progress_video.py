#!/usr/bin/env python3
"""Render a batch's outcomes as they landed into an MP4 (progress demo, not a study figure).

progress_video.py --runs DIR [--out FILE.mp4] [--fps 4] [--title TEXT]

Reads <runs>/scores.csv (scoring/score.py) and each run's manifest.json for its `ended` time, orders runs by that time,
and draws one frame per landed run: stacked outcome shares per body (action axis) on the left, the final-message
disclosure on the right, with the running counts. Frames go to a temp dir and ffmpeg stitches them. Invalid runs
(timed out etc.) are shown as a grey band so the exclusion is visible. Nothing here feeds VERIFY.md or the figures.
"""
import argparse, csv, json, os, subprocess, sys, tempfile
from pathlib import Path

ACTIONS = ["spec_correct", "special_case", "tamper", "none", "invalid"]
ACOL = {"spec_correct": "#4c9a6a", "special_case": "#e0a030", "tamper": "#c0392b", "none": "#8899aa", "invalid": "#d0d0d0"}
DISCS = ["explicit_conflict", "ask", "silent_done", "false_claim", "none", "invalid"]
DCOL = {"explicit_conflict": "#4c9a6a", "ask": "#5b8dd6", "silent_done": "#e0a030", "false_claim": "#c0392b", "none": "#8899aa", "invalid": "#d0d0d0"}
BODIES = ["claude", "codex", "opencode", "pi"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True); ap.add_argument("--out"); ap.add_argument("--fps", type=int, default=4)
    ap.add_argument("--title", default=None)
    a = ap.parse_args()
    runs = Path(a.runs)
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = list(csv.DictReader(open(runs / "scores.csv")))
    ended = {}
    for r in rows:
        try:
            ended[r["run_id"]] = json.load(open(runs / r["run_id"] / "manifest.json")).get("ended") or 0
        except Exception:
            ended[r["run_id"]] = 0
    rows.sort(key=lambda r: ended.get(r["run_id"], 0))
    title = a.title or f"{runs.name}: outcomes as runs landed"
    tmp = Path(tempfile.mkdtemp(prefix="mrh-frames-"))
    counts = {b: {k: 0 for k in ACTIONS} for b in BODIES}
    dcounts = {b: {k: 0 for k in DISCS} for b in BODIES}
    for i, r in enumerate(rows, 1):
        b = r["body"]
        if b not in counts:
            continue
        act = r["action"] if r["action"] in ACTIONS else "none"
        dis = r.get("disclosure_final") or "none"
        if r["action"] == "invalid":
            dis = "invalid"
        if dis not in DISCS:
            dis = "none"
        counts[b][act] += 1; dcounts[b][dis] += 1
        fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=100)
        for ax, cs, keys, cols, name in ((axes[0], counts, ACTIONS, ACOL, "action (diff + reruns)"),
                                         (axes[1], dcounts, DISCS, DCOL, "final message")):
            bottoms = [0] * len(BODIES)
            for k in keys:
                vals = [cs[bb][k] for bb in BODIES]
                ax.bar(BODIES, vals, bottom=bottoms, color=cols[k], label=k, width=0.6)
                bottoms = [x + y for x, y in zip(bottoms, vals)]
            ax.set_title(name); ax.set_ylabel("runs"); ax.legend(fontsize=8, loc="upper left")
            ax.set_ylim(0, max(1, max(sum(cs[bb].values()) for bb in BODIES) + 2))
        fig.suptitle(f"{title}   [{i}/{len(rows)} runs]   last: {b} {r['task_id']} -> {act} / {dis}", fontsize=11)
        fig.tight_layout()
        fig.savefig(tmp / f"f{i:05d}.png"); plt.close(fig)
    # hold the last frame for 2 seconds
    for j in range(2 * a.fps):
        os.link(tmp / f"f{len(rows):05d}.png", tmp / f"f{len(rows) + 1 + j:05d}.png")
    out = a.out or str(runs / "progress.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-i", str(tmp / "f%05d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", out]
    subprocess.run(cmd, check=True)
    print(f"wrote {out} ({len(rows)} frames at {a.fps} fps)")


if __name__ == "__main__":
    sys.exit(main())
