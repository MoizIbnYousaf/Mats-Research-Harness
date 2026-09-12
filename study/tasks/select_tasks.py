#!/usr/bin/env python3
"""Pick the full-study task set from the twin screens (PLAN line 27 "30 tasks"; exclusion rule "tasks whose twin fails
in every arm excluded before analysis"; LOG Sept 4 03:35 "the full-study task mix is set after the twins land").

select_tasks.py --kill study/runs/kill-tasks.txt --twins DIR [--twins DIR ...] [--n 30] [--max-oneoff 10] --out FILE

Rule, fixed before any impossible-task result is read: keep every kill-test task; then add tasks in descending order
of passing-twin count (ties broken by task number, lowest first) until --n, never more than --max-oneoff from the
oneoff split; a task with no passing twin in any screen is never added. Prints the table it decided on.
"""
import argparse, json, glob, os, re
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kill", default=str(STUDY / "runs" / "kill-tasks.txt")); ap.add_argument("--twins", action="append", required=True)
    ap.add_argument("--n", type=int, default=30); ap.add_argument("--max-oneoff", type=int, default=10); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    kill = [l.strip() for l in open(a.kill) if l.strip()]
    kill_ids = {os.path.basename(k) for k in kill}
    stats = {}
    for d in a.twins:
        for m in glob.glob(str(Path(d) / "*" / "manifest.json")):
            r = json.load(open(m))
            if r.get("kind") != "twin":
                continue
            tid = r["task_id"].replace("-twin", "-impossible")
            s = stats.setdefault(tid, {"pass": 0, "fail": 0, "timeout": 0, "path": r.get("task_path")})
            s["pass" if (r["status"] == "completed" and r.get("visible_pass")) else ("timeout" if r["status"] == "timed_out" else "fail")] += 1
    def split_of(tid):
        for sub in ("ib", "ib-oneoff"):
            if (STUDY / "tasks" / sub / tid).exists():
                return "oneoff" if sub == "ib-oneoff" else "conflicting", STUDY / "tasks" / sub / tid
        return None, None
    chosen = list(kill)
    oneoff = sum(1 for k in kill if "ib-oneoff" in k)
    cands = [(tid, s) for tid, s in stats.items() if tid not in kill_ids and s["pass"] > 0]
    cands.sort(key=lambda x: (-x[1]["pass"], int(re.search(r"_(\d+)", x[0]).group(1))))
    for tid, s in cands:
        if len(chosen) >= a.n:
            break
        sp, path = split_of(tid)
        if path is None:
            continue
        if sp == "oneoff" and oneoff >= a.max_oneoff:
            continue
        chosen.append(str(path)); oneoff += sp == "oneoff"
    with open(a.out, "w") as f:
        f.write("\n".join(chosen) + "\n")
    print(f"{len(chosen)} tasks ({oneoff} oneoff) -> {a.out}")
    for c in chosen:
        tid = os.path.basename(c); s = stats.get(tid, {"pass": "-", "fail": "-", "timeout": "-"})
        print(f"  {'kill ' if c in kill else 'added'} {('oneoff' if 'ib-oneoff' in c else 'confl.'):7s} {tid:24s} twins pass {s['pass']} fail {s['fail']} timeout {s['timeout']}")


if __name__ == "__main__":
    main()
