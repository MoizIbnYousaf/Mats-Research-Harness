#!/usr/bin/env python3
"""Seeded random order over tasks x bodies x states x samples, concurrency-capped, resumable (PLAN v3 lines 41, 47,
57-68). Each cell is one run.py call.

batch.py --tasks DIR|GLOB... --bodies B... [--states A B fixable] [--level N] [--samples N] [--concurrency 8]
         [--out DIR] [--seed 0] [--model SLUG] [--sandbox docker|host] [--resume] [--max-runs N] [--dry-run]
Twins run in State A with one sample (PLAN line 62). Cells are written to <out>/order.jsonl; --resume skips a cell
when a manifest with the same split.task_id / body / state / level / sample and `status: completed` already exists
under <out> (a dead cell, any other status, is run again); failed cells go to <out>/batch-errors.log; the batch
refuses to start when the cell count exceeds --max-runs (--dry-run still prints the plan so the cap can be sized).
A cell whose task lacks the environment dir for its state (environment-B/, environment-fixable/) is skipped and
counted, never scheduled; a twin reached through two task dirs (same split.task_id) is scheduled once. --level,
--bodies, --states and --sandbox take exactly the values run.py takes. After DEAD_ABORT consecutive cells that did
not complete (run.py failed, or its manifest status is not `completed`: an exhausted key, a missing binary, an empty
sandbox) the batch stops scheduling and exits 2, so a broken setup cannot burn a whole block.
"""
import argparse, glob, json, os, random, subprocess, sys, threading, tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_env import BODIES  # noqa: E402
from rerun import ENV_DIRS  # noqa: E402

STUDY = Path(__file__).resolve().parent.parent
RUN_PY = Path(__file__).resolve().parent / "run.py"
DEAD_ABORT = 5  # consecutive launch_failed / upstream_error / run.py failures; timed_out is not dead


def expand_tasks(specs: list[str]) -> list[Path]:
    out: list[Path] = []
    for s in specs:
        hits = [Path(p) for p in sorted(glob.glob(s))] or [Path(s)]
        for h in hits:
            h = h.resolve()
            if (h / "task.toml").exists():
                out.append(h)
            elif h.is_dir():
                out += sorted(d.resolve() for d in h.iterdir() if (d / "task.toml").exists())
    return list(dict.fromkeys(out))


def task_meta(task: Path) -> dict:
    t = tomllib.loads((task / "task.toml").read_text())["task"]
    return {"task_id": t["id"], "kind": t.get("kind", "impossible"), "split": t.get("split", "")}


def cells_for(tasks: list[Path], bodies: list[str], states: list[str], level: int, samples: int, seed: int) -> tuple[list[dict], list[str]]:
    """(cells in seeded random order, skipped) where skipped lists `task_id:state` for every cell whose environment
    dir is missing (run.py would refuse it) and `task_id` once for a duplicate task dir (same split.task_id)."""
    cells = []; skipped = []; seen: set[tuple] = set()
    for task in tasks:
        m = task_meta(task)
        st = ["A"] if m["kind"] == "twin" else states
        ns = 1 if m["kind"] == "twin" else samples
        for state in st:
            if not (task / ENV_DIRS[state]).is_dir():
                skipped.append(f"{m['task_id']}:{state}"); continue
            for body in bodies:
                for s in range(ns):
                    c = {"task": str(task), "task_id": m["task_id"], "split": m["split"], "kind": m["kind"],
                         "body": body, "state": state, "level": level, "sample": s}
                    if cell_key(c) in seen:
                        if m["task_id"] not in skipped:
                            skipped.append(m["task_id"])
                        continue
                    seen.add(cell_key(c)); cells.append(c)
    random.Random(seed).shuffle(cells)
    return cells, skipped


def existing_keys(out: Path) -> set[tuple]:
    """Cells already done under out: only a manifest with status `completed` counts (a dead run is redone on --resume)."""
    keys = set()
    if not out.exists():
        return keys
    for mf in out.glob("*/manifest.json"):
        try:
            m = json.loads(mf.read_text())
            if m.get("status") != "completed":
                continue
            keys.add((m.get("split", ""), m.get("task_id"), m.get("body"), m.get("state"), m.get("level"), m.get("sample")))
        except Exception:
            continue
    return keys


def cell_key(c: dict) -> tuple:
    return (c["split"], c["task_id"], c["body"], c["state"], c["level"], c["sample"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks", nargs="+", required=True); ap.add_argument("--bodies", nargs="+", required=True, choices=BODIES)
    ap.add_argument("--states", nargs="+", default=["A"], choices=["A", "B", "fixable"])
    ap.add_argument("--level", type=int, default=1, choices=(1, 2, 3)); ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=8); ap.add_argument("--out", default=str(STUDY / "runs"))
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--model", default="deepseek/deepseek-v4-flash-0731")
    ap.add_argument("--sandbox", default=None, choices=("docker", "host")); ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-runs", type=int, default=None); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args(argv)
    tasks = expand_tasks(a.tasks)
    if not tasks:
        sys.exit("batch: no task dirs found")
    cells, skipped = cells_for(tasks, a.bodies, a.states, a.level, a.samples, a.seed)
    skip_note = f"; {len(skipped)} skipped (missing environment dir or duplicate task dir): {' '.join(skipped)}" if skipped else ""
    out = Path(a.out).resolve()
    if a.resume:
        have = existing_keys(out); cells = [c for c in cells if cell_key(c) not in have]
    over = a.max_runs is not None and len(cells) > a.max_runs
    if a.dry_run:
        for c in cells:
            print(json.dumps(c))
        print(f"batch: {len(cells)} cells ({len(tasks)} tasks x {len(a.bodies)} bodies x states {','.join(a.states)} x {a.samples} samples; twins A x 1){skip_note}"
              + (f"; exceeds --max-runs {a.max_runs}, a real batch refuses" if over else ""))
        return 0
    if over:
        sys.exit(f"batch: {len(cells)} cells exceed --max-runs {a.max_runs}; refusing")
    if skipped:
        print(f"batch: {len(cells)} cells{skip_note}", file=sys.stderr)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "order.jsonl", "a") as f:
        for c in cells:
            f.write(json.dumps(c) + "\n")
    errlog = out / "batch-errors.log"
    lock = threading.Lock(); dead = [0]; aborted = threading.Event()

    def settle(ok: bool):
        with lock:
            dead[0] = 0 if ok else dead[0] + 1
            if dead[0] >= DEAD_ABORT:
                aborted.set()

    def one(c: dict) -> str:
        if aborted.is_set():
            return json.dumps({"cell": cell_key(c), "note": "not run: batch aborted"})
        cmd = [a.python, str(RUN_PY), "--task", c["task"], "--body", c["body"], "--state", c["state"], "--level",
               str(c["level"]), "--sample", str(c["sample"]), "--out", str(out), "--model", a.model]
        if a.sandbox:
            cmd += ["--sandbox", a.sandbox]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(STUDY.parent))
        if r.returncode != 0:
            with open(errlog, "a") as f:
                f.write(f"=== {cell_key(c)} exit {r.returncode}\n{r.stderr}\n")
            settle(False)
            return json.dumps({"cell": cell_key(c), "error": r.returncode, "stderr_tail": r.stderr[-300:]})
        line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        try:
            status = json.loads(line).get("status")
        except Exception:
            status = None
        settle(status in ("completed", "timed_out"))  # a timed-out run is the setup working (LOG Sept 4 03:55); only launch/upstream failures count as dead
        return line or json.dumps({"cell": cell_key(c), "note": "no output"})

    with ThreadPoolExecutor(a.concurrency) as ex:
        for line in ex.map(one, cells):
            print(line, flush=True)
    if aborted.is_set():
        print(f"batch: aborted after {DEAD_ABORT} consecutive cells that did not complete (see manifests' status and "
              f"{errlog}); fix the setup and rerun with --resume", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
