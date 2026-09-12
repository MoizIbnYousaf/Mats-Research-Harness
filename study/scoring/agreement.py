"""Agreement between the hand labels and the scorer, blind subset reported apart from the confirm set.

    python study/scoring/agreement.py

perception.csv / outcome.csv: rows still marked PROPOSED are not counted. blind = labelled with the proposal hidden
(scripts/label_server.py BLIND); proposal_agree = Moiz's hand label came out the same as the visible proposal. false_claims.csv: hand verdict
vs the detector. cot_tally.csv: counts of the three reading questions, priority 1 and 2 first.
"""
import csv
from collections import Counter
from pathlib import Path

LAB = Path(__file__).resolve().parents[1] / "labels"


def truthy(x):
    return str(x).strip().lower() == "true"


def sheet(name):
    return list(csv.DictReader(open(LAB / name)))


def report(name, hand_scorer_pairs):
    rows = [r for r in sheet(name) if r[hand_scorer_pairs[0][0]].strip() and not (r.get("notes") or "").startswith("PROPOSED")]
    print(f"\n== {name}: {len(rows)} labelled of {len(sheet(name))}")
    for hand, scorer in hand_scorer_pairs:
        agree = sum(1 for r in rows if r[hand] == r[scorer])
        print(f"   {hand:28s} vs {scorer:28s} agree {agree}/{len(rows)}")
    for tag in ("true", "false"):
        sub = [r for r in rows if r.get("blind") == tag]
        if sub:
            allagree = sum(1 for r in sub if all(r[h] == r[sc] for h, sc in hand_scorer_pairs))
            pagree = sum(1 for r in sub if r.get("proposal_agree") == "true")
            print(f"   {'blind' if tag == 'true' else 'confirm-set'} rows: {len(sub)}; all fields agree with scorer {allagree}/{len(sub)}; hand label same as the visible proposal {pagree}/{len(sub)}")
    diffs = [r["run_id"] for r in rows if not all(r[h] == r[sc] for h, sc in hand_scorer_pairs)]
    if diffs:
        print("   disagreements:", *diffs, sep="\n     ")


def main():
    report("perception.csv", [("hand_observed_conflict", "scorer_observed_conflict"), ("hand_knowing", "scorer_knowing")])
    report("outcome.csv", [("hand_action", "scorer_action"), ("hand_disclosure_final", "scorer_disclosure_final")])
    fc = [r for r in sheet("false_claims.csv") if r["hand_verdict"].strip() and not (r.get("notes") or "").startswith("PROPOSED")]
    print(f"\n== false_claims.csv: {len(fc)} confirmed of {len(sheet('false_claims.csv'))}; verdicts {dict(Counter(r['hand_verdict'] for r in fc))}; hand label differed from the visible proposal in {sum(1 for r in fc if r['hand_verdict'] != r['read_verdict'])}")
    cot = sheet("cot/cot_tally.csv")
    done = [r for r in cot if r["hand_names_wrong_test_before_edit"].strip()]
    print(f"\n== cot_tally.csv: {len(done)} read of {len(cot)}; by priority {dict(sorted(Counter(r['priority'] for r in done).items()))}")
    for k in ("hand_names_wrong_test_before_edit", "hand_cites_cue", "hand_thinks_tested"):
        print(f"   {k:36s} {dict(Counter(r[k] for r in done))}")
    p1 = [r for r in done if r["priority"] == "1"]
    if p1:
        print(f"   priority 1 (level-2 Pi/Codex sketchy, {len(p1)} read): names wrong test first {sum(truthy(r['hand_names_wrong_test_before_edit']) for r in p1)}, cites cue {sum(truthy(r['hand_cites_cue']) for r in p1)}, thinks tested {sum(truthy(r['hand_thinks_tested']) for r in p1)}")


if __name__ == "__main__":
    main()
