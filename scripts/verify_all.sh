#!/bin/sh
# Regenerate every audit file from the current code state (no runs). Run after any scorer or label change.
set -e
cd "$(dirname "$0")/.."
for d in pooled-all pooled-L2; do
  node bin/mrh.js verify --runs study/runs/$d --labels study/labels --prompts study/prompts --out study/runs/$d/VERIFY.md >/dev/null
  {
    echo
    echo "## Strict definition with the read false-claim verdicts (Sept 5; study/labels/false_claims.csv)"
    echo
    echo "    python3 study/scoring/attrition.py --runs study/runs/$d --state A --level $( [ $d = pooled-L2 ] && echo 2 || echo 1 ) --strict"
    python3 study/scoring/attrition.py --runs study/runs/$d --state A --level $( [ $d = pooled-L2 ] && echo 2 || echo 1 ) --strict | sed 's/^/    /'
    echo
    echo "    python3 study/scoring/perception_split.py --runs study/runs/$d --state A --level $( [ $d = pooled-L2 ] && echo 2 || echo 1 ) --strict"
    python3 study/scoring/perception_split.py --runs study/runs/$d --state A --level $( [ $d = pooled-L2 ] && echo 2 || echo 1 ) --strict | sed 's/^/    /'
    echo
    echo "    python3 study/scoring/agreement.py"
    python3 study/scoring/agreement.py | sed 's/^/    /'
  } >> study/runs/$d/VERIFY.md
  cp -f study/runs/$d/VERIFY.md study/VERIFY-$d.md
done
python3 study/scoring/gate.py --runs study/runs/pooled-A --state-b study/runs/pooled-B --fixable study/runs/pooled-fixable --strict > study/runs/pooled-all/GATE-strict.txt
uv run --quiet --with matplotlib python3 study/scoring/ladder_figure.py --runs study/runs/pooled-A study/runs/pooled-L2 study/runs/level3 --strict --out study/figures/fig_ladder_strict_30 >/dev/null 2>&1 || true
uv run --quiet --with matplotlib python3 study/scoring/fig_paired_split.py --l1 study/runs/pooled-A --l2 study/runs/pooled-L2 --out study/figures >/dev/null 2>&1 || true
echo "audit files regenerated: study/VERIFY-pooled-all.md, study/VERIFY-pooled-L2.md, study/runs/pooled-all/GATE-strict.txt, figures"
