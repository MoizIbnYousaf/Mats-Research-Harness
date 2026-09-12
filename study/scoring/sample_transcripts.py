#!/usr/bin/env python3
"""Random, not cherry-picked, transcripts for the write-up (Neel: "include some randomly selected qualitative examples ...
Randomly selected, not cherry-picked"; PLAN framing rule 6). Draws --n valid runs uniformly from the given runs dirs
with a fixed seed, writes one excerpt per run (same format as the label kit) and an index with the seed and the command.

sample_transcripts.py --runs DIR [--runs DIR ...] --n 10 --seed 7 --out study/samples/random
"""
import argparse, csv, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_label_sheets import load, excerpt  # noqa: E402


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--runs", action="append", required=True); ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=7); ap.add_argument("--out", default="study/samples/random"); a = ap.parse_args()
    rows = []
    for d in a.runs:
        rows += load(d)
    rows.sort(key=lambda r: r["run_id"])
    rng = random.Random(a.seed); pick = rng.sample(rows, min(a.n, len(rows)))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for r in pick:
        excerpt(r, out)
    with open(out / "INDEX.md", "w") as f:
        f.write(f"# {len(pick)} random transcripts (seed {a.seed}, uniform over {len(rows)} valid runs in {', '.join(a.runs)})\n\n")
        f.write(f"Command: `python study/scoring/sample_transcripts.py {' '.join('--runs ' + d for d in a.runs)} --n {a.n} --seed {a.seed}`\n\n")
        f.write("| run_id | body | state | action | tamper kind | final disclosure |\n|---|---|---|---|---|---|\n")
        for r in pick:
            f.write(f"| {r['run_id']} | {r['body']} | {r.get('state')} | {r.get('action')} | {r.get('tamper_kind','')} | {r.get('disclosure_final')} |\n")
    print(f"wrote {len(pick)} excerpts to {out}")


if __name__ == "__main__":
    main()
