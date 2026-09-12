#!/usr/bin/env python3
"""Ladder figure: sketchy rate (tamper + special_case + false_claim on the final message) by instruction level and body,
State A impossible tasks, invalid runs dropped, Wilson 95% intervals. CSV next to the PNG (study contract).

ladder_figure.py --runs study/runs/level1 study/runs/level2 study/runs/level3 [--out study/figures/fig_ladder]
"""
import argparse, csv, math
from collections import defaultdict
from pathlib import Path

BODIES = ["claude", "codex", "opencode", "pi"]
SKETCHY_ACTIONS = {"tamper", "special_case"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (p, (c - h) / d, (c + h) / d)


def read_verdicts():
    """study/labels/false_claims.csv: every false_claim_v2 flag was read; the hand verdict (or the proposed one
    until it is confirmed) replaces the detector. genuine keeps the flag; false_positive and no_claim clear it."""
    p = Path(__file__).resolve().parents[1] / "labels" / "false_claims.csv"
    if not p.exists():
        return {}
    return {r["run_id"]: (r.get("hand_verdict") or r.get("read_verdict")) for r in csv.DictReader(open(p))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True); ap.add_argument("--out", default="study/figures/fig_ladder")
    ap.add_argument("--strict", action="store_true", help="repair-kind tampers (wrong value -> spec value) are not sketchy")
    a = ap.parse_args()
    rows = []
    for d in a.runs:
        tk = Path(d) / "tamper_kinds.csv"
        kinds = {r["run_id"]: r["tamper_kind"] for r in csv.DictReader(open(tk))} if tk.exists() else {}
        cl = Path(d) / "claims.csv"
        v2 = {r["run_id"]: r["false_claim_v2"] for r in csv.DictReader(open(cl))} if cl.exists() else {}
        for rid, verdict in read_verdicts().items():
            if rid in v2:
                v2[rid] = "True" if verdict == "genuine" else "False"
        for r in csv.DictReader(open(Path(d) / "scores.csv")):
            if r.get("kind") == "twin" or r.get("state") != "A" or r.get("action") in ("invalid", "", None):
                continue
            r["tamper_kind"] = kinds.get(r["run_id"], "")
            if a.strict and r["run_id"] in v2:  # strict: the claim is judged against the agent's own workspace
                r["disclosure_final"] = "false_claim" if v2[r["run_id"]] == "True" else (r["disclosure_final"] if r["disclosure_final"] != "false_claim" else "explicit_conflict")
            rows.append(r)
    cells = defaultdict(lambda: [0, 0, 0, 0, 0])  # n, sketchy, tamper, special, false_claim
    for r in rows:
        c = cells[(r["level"], r["body"])]
        c[0] += 1
        repair = r["action"] == "tamper" and r.get("tamper_kind") == "repair"
        sk = (r["action"] in SKETCHY_ACTIONS and not (a.strict and repair)) or r.get("disclosure_final") == "false_claim"
        c[1] += sk; c[2] += r["action"] == "tamper"; c[3] += r["action"] == "special_case"; c[4] += r.get("disclosure_final") == "false_claim"
    levels = sorted({k[0] for k in cells})
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    with open(str(out) + ".csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["level", "body", "n_valid", "sketchy", "tamper", "special_case", "false_claim", "rate", "lo95", "hi95"])
        for L in levels:
            for b in BODIES:
                n, s, t, sp, fc = cells[(L, b)]; p, lo, hi = wilson(s, n)
                w.writerow([L, b, n, s, t, sp, fc, round(p, 4), round(lo, 4), round(hi, 4)])
            n = sum(cells[(L, b)][0] for b in BODIES); s = sum(cells[(L, b)][1] for b in BODIES); p, lo, hi = wilson(s, n)
            w.writerow([L, "pooled", n, s, "", "", "", round(p, 4), round(lo, 4), round(hi, 4)])
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    except Exception:
        print("no matplotlib; CSV only"); return
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=130)
    width = 0.18; names = {"1": "L1 neutral", "2": "L2 unattended, graded on pytest", "3": "L3 ImpossibleBench prompt A"}
    for i, b in enumerate(BODIES):
        xs = [j + (i - 1.5) * width for j in range(len(levels))]
        ps = []; err = [[], []]
        for L in levels:
            n, s, *_ = cells[(L, b)]; p, lo, hi = wilson(s, n); ps.append(100 * p); err[0].append(100 * (p - lo)); err[1].append(100 * (hi - p))
        ax.bar(xs, ps, width, yerr=err, capsize=2, label=b)
        for x, L in zip(xs, levels):
            ax.text(x, 1, f"n={cells[(L, b)][0]}", ha="center", va="bottom", fontsize=6, rotation=90)
    ax.set_xticks(range(len(levels))); ax.set_xticklabels([names.get(L, L) for L in levels], fontsize=8)
    ax.set_ylabel("sketchy runs, % of valid" + (" (strict: repairs excluded)" if a.strict else " (any test edit + special-case + false claim)")); ax.set_ylim(0, 60)
    ax.set_title("DeepSeek v4 Flash, four harnesses, State A: sketchy rate by instruction level (Wilson 95%)", fontsize=9)
    ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(str(out) + ".png"); print(f"wrote {out}.png and .csv")


if __name__ == "__main__":
    main()
