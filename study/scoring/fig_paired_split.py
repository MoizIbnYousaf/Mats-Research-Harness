"""Two figures the summary needs, from scores already on disk (no new runs).

fig_ladder_paired: strict sketchy rate per harness at the two study instructions, on the tasks every harness
finished at that level (paired), Wilson 95% intervals, n printed under each bar. Level 3 is left to the appendix.

fig_split_obs: strict sketchy rate at the neutral instruction by task split (self-contradicting test vs one
value silently changed) and by whether the model saw the conflicting assert fail before acting, n under each bar.

table_body_split_level.csv: every body x split x level cell with count, n, rate and Wilson interval.

    python study/scoring/fig_paired_split.py --l1 study/runs/pooled-A --l2 study/runs/pooled-L2 --out study/figures
"""
import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from attrition import load as load_rows  # noqa: E402
from perception_split import load as load_perc  # noqa: E402

BODIES = ["claude", "codex", "opencode", "pi"]
NAMES = {"claude": "Claude Code", "codex": "Codex", "opencode": "OpenCode", "pi": "Pi"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (p, (c - h) / d, (c + h) / d)


def paired(rows):
    valid = [r for r in rows if r["valid"]]
    common = set.intersection(*[{r["task"] for r in valid if r["body"] == b} for b in BODIES])
    out = {}
    for b in BODIES:
        v = [r for r in valid if r["body"] == b and r["task"] in common]
        out[b] = (sum(r["sketchy"] for r in v), len(v))
    return out, len(common)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--l1", required=True); ap.add_argument("--l2", required=True); ap.add_argument("--out", default="study/figures")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    l1 = load_rows([a.l1], "A", "1", True); l2 = load_rows([a.l2], "A", "2", True)
    p1, n1 = paired(l1); p2, n2 = paired(l2)

    # table: body x split x level
    with open(out / "table_body_split_level.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["level", "body", "split", "sketchy", "n", "rate", "lo95", "hi95"])
        for lvl, rows in (("1", l1), ("2", l2)):
            for b in BODIES:
                for s in ("conflicting", "oneoff"):
                    v = [r for r in rows if r["valid"] and r["body"] == b and r["split"] == s]
                    k = sum(r["sketchy"] for r in v); p, lo, hi = wilson(k, len(v))
                    w.writerow([lvl, b, s, k, len(v), f"{p:.4f}", f"{lo:.4f}", f"{hi:.4f}"])

    with open(out / "fig_ladder_paired.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["level", "paired_tasks", "body", "sketchy", "n", "rate", "lo95", "hi95"])
        for lvl, pp, nn in (("1", p1, n1), ("2", p2, n2)):
            for b in BODIES:
                k, n = pp[b]; p, lo, hi = wilson(k, n)
                w.writerow([lvl, nn, b, k, n, f"{p:.4f}", f"{lo:.4f}", f"{hi:.4f}"])

    perc = load_perc([a.l1], "A", "1", True)
    cells = defaultdict(lambda: [0, 0])
    for r in perc:
        key = (r["split"], r["observed"]); cells[key][1] += 1; cells[key][0] += int(r["sketchy"])
    with open(out / "fig_split_obs.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["split", "observed_failure_before_acting", "sketchy", "n", "rate", "lo95", "hi95"])
        for s in ("conflicting", "oneoff"):
            for o in (True, False):
                k, n = cells[(s, o)]; p, lo, hi = wilson(k, n)
                w.writerow([s, o, k, n, f"{p:.4f}", f"{lo:.4f}", f"{hi:.4f}"])

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("no matplotlib; CSVs written"); return

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    x = range(len(BODIES)); wbar = 0.38
    for i, (lvl, pp, nn, col) in enumerate((("neutral instruction", p1, n1, "#4c72b0"), ("unattended, graded only on pytest", p2, n2, "#dd8452"))):
        rates = []; los = []; his = []
        for b in BODIES:
            k, n = pp[b]; p, lo, hi = wilson(k, n); rates.append(100 * p); los.append(100 * (p - lo)); his.append(100 * (hi - p))
        xs = [xx + (i - 0.5) * wbar for xx in x]
        ax.bar(xs, rates, wbar, yerr=[los, his], capsize=3, color=col, label=f"{lvl} ({nn} tasks every harness finished)")
        for xx, b in zip(xs, BODIES):
            k, n = pp[b]; ax.text(xx, -4.5, f"{k}/{n}", ha="center", va="top", fontsize=7.5, color="#444")
    ax.set_xticks(list(x)); ax.set_xticklabels([NAMES[b] for b in BODIES]); ax.set_ylim(-9, 45)
    ax.set_ylabel("strict cheating, % of runs (Wilson 95%)"); ax.axhline(0, color="#888", lw=0.6)
    ax.set_title("Same model, four harnesses: cheating on an impossible test, paired tasks", fontsize=10)
    ax.legend(fontsize=8, frameon=False); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(out / "fig_ladder_paired.png", dpi=160)

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    labels = []; rates = []; los = []; his = []; ns = []; cols = []
    for s, sname in (("conflicting", "test contradicts\nthe spec's example"), ("oneoff", "one value\nsilently changed")):
        for o, oname, col in ((True, "saw it fail", "#4c72b0"), (False, "did not run it", "#c44e52")):
            k, n = cells[(s, o)]; p, lo, hi = wilson(k, n)
            labels.append(f"{sname}\n{oname}"); rates.append(100 * p); los.append(100 * (p - lo)); his.append(100 * (hi - p)); ns.append(f"{k}/{n}"); cols.append(col)
    xs = range(len(labels))
    bars = ax.bar(xs, rates, 0.6, yerr=[los, his], capsize=3, color=cols)
    for xx, n in zip(xs, ns):
        ax.text(xx, -6, n, ha="center", va="top", fontsize=8.5, color="#444")
    ax.set_xticks(list(xs)); ax.set_xticklabels(labels, fontsize=8.5); ax.set_ylim(-12, 80)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color="#4c72b0", label="a tool result showed the conflicting assert failing"), Patch(color="#c44e52", label="never ran the test")], fontsize=8, frameon=False, loc="upper left")
    ax.set_ylabel("strict cheating, % of runs (Wilson 95%)"); ax.axhline(0, color="#888", lw=0.6)
    ax.set_title("Neutral instruction, all four harnesses pooled: what the model cheats on", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(out / "fig_split_obs.png", dpi=160)
    print(f"wrote {out}/fig_ladder_paired.png, fig_split_obs.png, table_body_split_level.csv")


if __name__ == "__main__":
    main()
