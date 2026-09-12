#!/usr/bin/env python3
"""Write tests/conflict.json per impossible task (PLAN v3 line 27: "the asserts that differ between test and
original_test, which the perception matcher uses").

build_conflict.py --tasks DIR... [--force]
For every task dir with kind=impossible: parse the `check()` body of environment/test_solution.py and
tests/hidden_original_test.py with ast; each Assert whose Compare calls `candidate(...)` is keyed by the call's source;
asserts whose expected value differs, or exist on one side only, are the conflicts. An empty list is refused, and so
is a visible test that defines no check() or carries a module-level assert (it would fail with NameError, or at import,
not on a conflict; the dataset's conflicting split has such rows).
"""
import argparse, ast, json, sys, tomllib
from pathlib import Path


def _asserts(src: str) -> list[tuple[str, str, int]]:
    """[(call_source, expected_source, lineno)] for every `assert candidate(...) == value` inside check()."""
    tree = ast.parse(src); out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "check":
            for st in ast.walk(node):
                if not isinstance(st, ast.Assert) or not isinstance(st.test, ast.Compare):
                    continue
                cmp = st.test; sides = [cmp.left] + list(cmp.comparators)
                call = next((s for s in sides if isinstance(s, ast.Call) and getattr(s.func, "id", None) == "candidate"), None)
                if call is None:
                    continue
                expected = next((s for s in sides if s is not call), None)
                key = ast.get_source_segment(src, call) or ast.unparse(call)
                exp_src = (ast.get_source_segment(src, expected) if expected is not None else None) or ast.unparse(expected)
                out.append((key, exp_src, st.lineno))
    return out


def malformed(src: str) -> str | None:
    """Why a test file cannot carry a conflict: no check() at module level, or an assert outside any function."""
    tree = ast.parse(src)
    if not any(isinstance(n, ast.FunctionDef) and n.name == "check" for n in tree.body):
        return "no def check()"
    if any(isinstance(n, ast.Assert) for n in tree.body):
        return "module-level assert"
    return None


def conflicts(visible_src: str, original_src: str) -> list[dict]:
    """Visible asserts whose (call, expected) pair is absent from the original test, plus original asserts whose call
    the visible test dropped. Duplicate calls with different values (the conflicting split) are handled pairwise."""
    v = _asserts(visible_src); o = _asserts(original_src)
    o_pairs = {(c, e) for c, e, _ in o}; v_pairs = {(c, e) for c, e, _ in v}
    o_by_call: dict[str, list[tuple[str, int]]] = {}
    for c, e, l in o:
        o_by_call.setdefault(c, []).append((e, l))
    v_calls = {c for c, _, _ in v}
    found = []
    for c, e, l in v:
        if (c, e) in o_pairs:
            continue
        orig = o_by_call.get(c, [])
        found.append({"call": c, "visible_expected": e, "original_expected": orig[0][0] if orig else None,
                      "visible_line": l, "original_line": orig[0][1] if orig else None})
    for c, e, l in o:
        if c not in v_calls:
            found.append({"call": c, "visible_expected": None, "original_expected": e, "visible_line": None, "original_line": l})
    return found


def build(task: Path, force: bool = False) -> dict | None:
    meta = tomllib.loads((task / "task.toml").read_text())["task"]
    if meta.get("kind") != "impossible":
        return None
    out = task / "tests" / "conflict.json"
    if out.exists() and not force:
        return json.loads(out.read_text())
    vis = task / "environment" / "test_solution.py"; orig = task / "tests" / "hidden_original_test.py"
    for f in (vis, orig):
        why = malformed(f.read_text())
        if why:
            raise SystemExit(f"{task}: {f.relative_to(task)} is malformed ({why}); every run would fail before any conflict, refusing")
    c = conflicts(vis.read_text(), orig.read_text())
    if not c:
        raise SystemExit(f"{task}: no conflicting asserts between {vis.name} and {orig.name}; refusing to write an empty conflict.json")
    rec = {"entry_point": meta.get("entry_point", ""), "split": meta.get("split", ""), "conflicts": c}
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks", nargs="+", required=True, help="task dirs or parents holding task dirs")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv); n = 0
    for root in a.tasks:
        root = Path(root)
        dirs = [root] if (root / "task.toml").exists() else sorted(d for d in root.iterdir() if (d / "task.toml").exists())
        for d in dirs:
            rec = build(d, a.force)
            if rec is not None:
                n += 1; print(f"{d}: {len(rec['conflicts'])} conflicting assert(s)")
    print(f"build_conflict: {n} task(s)")


if __name__ == "__main__":
    main()
