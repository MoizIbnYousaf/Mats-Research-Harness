"""Every number in a draft, checked against the numbers the repository can vouch for.

    python3 scripts/doc_numbers.py DRAFT.txt        # or:  pbpaste | python3 scripts/doc_numbers.py -

Known numbers come from docs/TIMER-LEDGER.md and the two
VERIFY files. A number that appears nowhere in those is not necessarily wrong (the draft may round), but it is the
one to look up by hand. Fractions like 16/17 are matched as fractions; percentages as the integer percent.
"""
import glob
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (["docs/TIMER-LEDGER.md", "docs/methods.md", "study/VERIFY-pooled-all.md",
            "study/VERIFY-pooled-L2.md", "study/VERIFY-level1-kill-test.md"]
           + sorted(glob.glob("study/figures/*.csv"))
           + sorted(glob.glob("study/labels/*.csv")))
FRAC = re.compile(r"\b(\d{1,4})\s*/\s*(\d{1,4})\b")
PCT = re.compile(r"\b(\d{1,3})(?:\.\d+)?\s*%")
NUM = re.compile(r"(?<![\d/.])\$?\b(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\b(?![\d/])")

def numbers(text):
    fr = {f"{a}/{b}" for a, b in FRAC.findall(text)}
    pc = {f"{p}%" for p in PCT.findall(text)}
    plain = {n.replace(",", "") for n in NUM.findall(text)}
    return fr, pc, plain

known_fr, known_pc, known_plain = set(), set(), set()
for s in SOURCES:
    p = ROOT / s
    if p.exists():
        a, b, c = numbers(p.read_text()); known_fr |= a; known_pc |= b; known_plain |= c
# percentages implied by known fractions, rounded either way
for f in list(known_fr):
    a, b = map(int, f.split("/"))
    if b:
        v = 100 * a / b
        known_pc |= {f"{int(v)}%", f"{round(v)}%"}

src = sys.argv[1] if len(sys.argv) > 1 else "-"
text = sys.stdin.read() if src == "-" else Path(src).read_text()
fr, pc, plain = numbers(text)
print(f"draft: {len(fr)} fractions, {len(pc)} percentages, {len(plain)} other numbers; summary word count {len(text.split())}")
def report(title, items, known, skip=()):
    bad = sorted(x for x in items if x not in known and x not in skip)
    ok = sorted(x for x in items if x in known)
    print(f"\n== {title}: {len(ok)} found in the repo files, {len(bad)} NOT found (look these up by hand)")
    if bad:
        print("   not found:", ", ".join(bad))
report("fractions", fr, known_fr)
report("percentages", pc, known_pc)
report("other numbers", plain, known_plain, skip={"2026", "12", "11", "9", "1", "2", "3", "4", "5", "6", "7", "8", "10"})
