#!/usr/bin/env python3
"""Build environment-B/ for a task from a reference solution (PLAN v3 line 29: State B seeds "a verified spec-correct
implementation that passes the hidden original tests and fails exactly the conflicting visible asserts").

build_state_b.py --task DIR --solution FILE [--python PY] [--force]
build_state_b.py --from-runs RUNS_DIR --tasks DIR... [--python PY] [--force] [--list-out FILE]

Checks, both required before anything is written, taken from the two reruns in runner/rerun.py (the same verifier the
scorer uses) on a temp work dir holding only the reference:
  1. the reference passes tests/hidden_original_test.py (rerun `original`);
  2. the visible test fails (rerun `visible`), and every failing assert is one of the calls in tests/conflict.json.
Writes environment-B/{README.md (state_b text), solution.py (reference), test_solution.py (the visible test)} and
records the solution sha under [state_b] in task.toml.

--from-runs (PLAN line 29: "Reference solutions come from the passing twin runs of factor 1"): for every impossible task
under --tasks, the twin runs in RUNS_DIR whose manifest has kind=twin, twin_of=<task id>, status="completed" and
visible_pass=true are tried in run-id order; the first `work_final/solution.py` that passes both checks becomes the
reference (task.toml records the run id). Tasks with no such twin, or whose twins all fail a check, are listed under
"excluded" and get no environment-B/; --list-out writes the built task dirs one per line for `mrh batch --tasks`.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, tomllib
from pathlib import Path

STUDY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STUDY / "runner"))
from rerun import reruns  # noqa: E402

PYTEST_ENV = {"NO_COLOR": "1", "PY_COLORS": "0"}


def _env() -> dict:
    e = {k: v for k, v in os.environ.items() if k != "FORCE_COLOR"}; e.update(PYTEST_ENV); return e


def run_pytest(python: str, solution: Path, test: Path, timeout: int = 180) -> tuple[bool, str]:
    """pytest -q on one solution/test pair in a temp dir; (passed, output). Used to read WHICH asserts fail; the
    pass/fail verdicts themselves come from runner/rerun.py."""
    with tempfile.TemporaryDirectory(prefix="hs-build-") as td:
        shutil.copy(solution, Path(td) / "solution.py"); shutil.copy(test, Path(td) / "test_solution.py")
        try:
            r = subprocess.run([python, "-m", "pytest", "test_solution.py", "-q", "-p", "no:cacheprovider", "--color=no"],
                               cwd=td, capture_output=True, text=True, timeout=timeout, env=_env())
        except subprocess.TimeoutExpired:
            return False, f"timeout after {timeout}s"
        return r.returncode == 0, r.stdout + r.stderr


def failing_calls(out: str) -> list[str]:
    """The `candidate(...)` calls on the assert lines pytest marks with `>`."""
    return [m.group(1) for m in re.finditer(r"^>\s+assert (candidate\(.*?\)) ==", out, re.M)]


def state_b_text() -> str:
    return (STUDY / "prompts" / "instructions" / "state_b.md").read_text().rstrip("\n") + "\n"


def rerun_reference(task: Path, solution: Path, python: str) -> dict:
    """The two reruns on a work dir that holds only the reference (State A's pristine visible test is copied in)."""
    with tempfile.TemporaryDirectory(prefix="hs-ref-") as td:
        work = Path(td) / "work"; work.mkdir(); shutil.copy(solution, work / "solution.py")
        shutil.copy(task / "environment" / "test_solution.py", work / "test_solution.py")
        return reruns(task, "A", work, python)


def check_reference(task: Path, solution: Path, python: str) -> dict:
    conflict = json.loads((task / "tests" / "conflict.json").read_text())
    r = rerun_reference(task, solution, python)
    _, out_vis = run_pytest(python, solution, task / "environment" / "test_solution.py")
    calls = failing_calls(out_vis)
    allowed = {c["call"] for c in conflict["conflicts"] if c.get("visible_expected") is not None}
    return {"original_pass": bool(r["original"]), "visible_pass": bool(r["visible"]), "rerun_error": r.get("error"),
            "failing_calls": calls, "only_conflicting": bool(calls) and all(c in allowed for c in calls),
            "out_vis": out_vis, "out_orig": r.get("original_out", "")}


def build(task: Path, solution: Path, python: str = sys.executable, force: bool = False, source: str = "") -> dict:
    task = task.resolve(); solution = solution.resolve()
    dest = task / "environment-B"
    if dest.exists() and not force:
        raise SystemExit(f"{dest} exists; use --force to rebuild")
    r = check_reference(task, solution, python)
    if r["rerun_error"]:
        raise SystemExit(f"refusing: rerun error {r['rerun_error']}")
    if not r["original_pass"]:
        raise SystemExit(f"refusing: reference fails the original tests\n{(r['out_orig'] or '')[-1500:]}")
    if r["visible_pass"]:
        raise SystemExit("refusing: reference passes the visible test, so the task is not impossible for it")
    if not r["only_conflicting"]:
        raise SystemExit(f"refusing: the visible failure is not on a conflicting assert (failing calls: {r['failing_calls']})\n{r['out_vis'][-1500:]}")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir()
    (dest / "README.md").write_text("# Task\n\n" + state_b_text())
    shutil.copy(solution, dest / "solution.py"); shutil.copy(task / "environment" / "test_solution.py", dest / "test_solution.py")
    sha = hashlib.sha256(solution.read_bytes()).hexdigest()[:16]
    toml = task / "task.toml"; s = toml.read_text()
    s = re.sub(r"\n\[state_b\][^\[]*", "\n", s).rstrip("\n") + (
        f'\n\n[state_b]\nsolution_sha = "{sha}"\nsource = "{source}"\nfailing_calls = {json.dumps(r["failing_calls"])}\n')
    toml.write_text(s)
    return {"dest": str(dest), "solution_sha": sha, "failing_calls": r["failing_calls"], "source": source}


def task_dirs(roots: list[str]) -> list[Path]:
    """Impossible task dirs: each root is a task dir or a parent of task dirs."""
    out = []
    for root in roots:
        root = Path(root).resolve()
        dirs = [root] if (root / "task.toml").exists() else sorted(d for d in root.iterdir() if (d / "task.toml").exists())
        for d in dirs:
            if tomllib.loads((d / "task.toml").read_text())["task"].get("kind", "impossible") == "impossible":
                out.append(d)
    return out


def twin_runs(runs: Path, task_id: str) -> list[tuple[Path, dict]]:
    """Run dirs under `runs` whose manifest is a completed, visible-passing twin of `task_id`, in run-id order."""
    accept = {task_id, task_id.removesuffix("-impossible")}
    found = []
    for mf in sorted(Path(runs).glob("*/manifest.json")):
        try:
            m = json.loads(mf.read_text())
        except Exception:
            continue
        if m.get("kind") == "twin" and m.get("twin_of") in accept and m.get("status") == "completed" \
                and m.get("visible_pass") is True and (mf.parent / "work_final" / "solution.py").exists():
            found.append((mf.parent, m))
    return sorted(found, key=lambda t: t[1].get("run_id", t[0].name))


def build_from_runs(runs: Path, roots: list[str], python: str = sys.executable, force: bool = False,
                    list_out: Path | None = None) -> dict:
    built = []; excluded = []
    for task in task_dirs(roots):
        tid = tomllib.loads((task / "task.toml").read_text())["task"]["id"]
        if (task / "environment-B").exists() and not force:
            built.append({"task": str(task), "source": "already built (use --force to rebuild)"}); continue
        twins = twin_runs(runs, tid); reasons = []
        if not twins:
            excluded.append({"task": str(task), "why": "no twin run with status=completed and visible_pass=true"}); continue
        for run_dir, m in twins:
            try:
                r = build(task, run_dir / "work_final" / "solution.py", python, force=True, source=m.get("run_id", run_dir.name))
            except SystemExit as e:
                reasons.append(f"{m.get('run_id', run_dir.name)}: {str(e).splitlines()[0]}"); continue
            built.append({"task": str(task), "source": r["source"], "solution_sha": r["solution_sha"], "failing_calls": r["failing_calls"]})
            break
        else:
            excluded.append({"task": str(task), "why": "; ".join(reasons)})
    if list_out is not None:
        Path(list_out).write_text("".join(b["task"] + "\n" for b in built))
    return {"built": built, "excluded": excluded}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task"); ap.add_argument("--solution")
    ap.add_argument("--from-runs", metavar="RUNS_DIR", help="take each task's reference from its passing twin run here")
    ap.add_argument("--tasks", nargs="*", default=[], help="with --from-runs: task dirs or parents holding task dirs")
    ap.add_argument("--list-out", default=None, help="with --from-runs: write the built task dirs, one per line")
    ap.add_argument("--python", default=sys.executable); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if a.from_runs:
        if not a.tasks:
            ap.error("--from-runs needs --tasks")
        r = build_from_runs(Path(a.from_runs), a.tasks, a.python, a.force, Path(a.list_out) if a.list_out else None)
        print(json.dumps(r, indent=1))
        print(f"build_state_b: {len(r['built'])} built, {len(r['excluded'])} excluded", file=sys.stderr)
        return 0
    if not a.task or not a.solution:
        ap.error("--task and --solution are required (or --from-runs with --tasks)")
    print(json.dumps(build(Path(a.task), Path(a.solution), a.python, a.force, source=str(Path(a.solution)))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
