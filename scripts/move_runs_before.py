#!/usr/bin/env python3
"""Move run dirs of one body that STARTED before a cutover time out of a batch dir, so `mrh batch --resume` runs those
cells again (a cell counts as done only when a manifest with status completed exists under --out).

move_runs_before.py --runs DIR [--runs DIR ...] --body claude --before EPOCH --to DIR

Used on Sept 4 05:00 EDT for the proxy's empty-completion retry (LOG): Claude Code runs archived before the fix could
end on an empty reply; they are kept under --to and excluded, and the same cells are rerun through the fixed proxy.
"""
import argparse, json, os, shutil
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", action="append", required=True); ap.add_argument("--body", required=True)
    ap.add_argument("--before", type=float, required=True); ap.add_argument("--to", required=True); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    moved = 0; kept = 0
    for d in a.runs:
        for m in sorted(Path(d).glob("*/manifest.json")):
            r = json.load(open(m))
            if r.get("body") != a.body:
                continue
            if (r.get("started") or 0) >= a.before:
                kept += 1; continue
            dest = Path(a.to) / Path(d).name / m.parent.name
            print(f"move {m.parent} -> {dest}")
            if not a.dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(m.parent), str(dest))
            moved += 1
    print(f"{a.body}: moved {moved} run dirs started before {a.before}, kept {kept}")


if __name__ == "__main__":
    main()
