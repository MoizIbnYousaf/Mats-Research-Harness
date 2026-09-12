#!/usr/bin/env python3
"""Walk a runs dir and write the perception record per run (PLAN v3 lines 30, 33; Verification items 3-5).

perceive.py --runs DIR [--out DIR/perception.csv]
Per run dir holding manifest.json: body antigravity -> parse_agy.parse_stream(stdout.log); otherwise
parse_proxy.parse_run(proxy.load_records(proxy/)): the `<run_id>__<n>__req.json` / `__resp.json` pairs the proxy writes
joined into one record per request, older single-file records passed through, and a file that does not
parse as JSON marked `_bad` (the parser flags the run). The conflict comes from <manifest.task_path>/tests/conflict.json
(twins: none). The row carries `state` and `level` from the manifest.
Writes <run>/assistant_text.txt (turn-separated), <run>/perception.json and one CSV row. <run>/final_message.txt is
written only when the body did not write its own (run.py copies codex's --output-last-message file there before this
script runs): a body-written file is never overwritten; the parser's text then goes to <run>/final_message.perceived.txt
and perception.json records final_message_source="cli" and final_message_matches_cli. A file this script wrote earlier
(perception.json says final_message_source="perceive") is rewritten on re-runs.
A run that fails to parse gets parse_error set and the walk continues. Prints `perceive: N runs, M parsed, E errors`;
exit 1 if E > 0.
"""
import argparse, csv, json, sys, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from perception import CSV_COLUMNS, Perception  # noqa: E402
from parse_proxy import parse_run  # noqa: E402
from parse_agy import parse_stream  # noqa: E402
from proxy import REC_RE, load_records  # noqa: E402


REPO = Path(__file__).resolve().parent.parent.parent


def resolve_task_path(task_path: str | None) -> Path | None:
    """Manifests from real runs hold absolute paths; the committed fixtures hold repo-relative ones."""
    if not task_path:
        return None
    p = Path(task_path)
    return p if p.is_absolute() else (REPO / p)


def load_conflict(task_path: str | None) -> dict:
    tp = resolve_task_path(task_path)
    if tp is None:
        return {"conflicts": []}
    p = tp / "tests" / "conflict.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {"conflicts": []}
    return {"conflicts": []}


def proxy_records(d: Path) -> list[dict]:
    """proxy.load_records plus the `_bad` marker on every record built from a file that is not valid JSON (a corrupt
    req or resp half marks its joined record; load_records itself only marks unpaired files)."""
    if not d.exists():
        return []
    bad: dict[str, str] = {}
    for f in sorted(d.glob("*.json")):
        try:
            json.loads(f.read_text())
        except Exception as e:
            m = REC_RE.match(f.name)
            bad[f"{m['base']}__{m['n']}" if m else f.name] = f"{f.name}: {e}"
    recs = load_records(d)
    for r in recs:
        if r.get("id") in bad and not r.get("_bad"):
            r["_bad"] = bad[r["id"]]
    return recs


def perceive_run(run: Path) -> Perception:
    m = json.loads((run / "manifest.json").read_text())
    conflict = load_conflict(m.get("task_path")) if m.get("kind") != "twin" else {"conflicts": []}
    body = m.get("body", "")
    if body == "antigravity":
        pin = m.get("agy_model") or m.get("model") or ""
        lines = (run / "stdout.log").read_text(errors="replace").splitlines() if (run / "stdout.log").exists() else []
        p = parse_stream(lines, conflict, pin)
    else:
        pin = m.get("model") or ""
        p = parse_run(proxy_records(run / "proxy"), conflict, pin)
    p.run_id = m.get("run_id", run.name); p.body = body
    p.state = "" if m.get("state") is None else str(m.get("state"))
    p.level = "" if m.get("level") is None else str(m.get("level"))
    return p


def _cli_final_message(run: Path) -> bool:
    """True when <run>/final_message.txt was written by the body (run.py's copy), not by an earlier perceive run."""
    fm = run / "final_message.txt"
    if not fm.exists():
        return False
    pj = run / "perception.json"
    if not pj.exists():
        return True    # run.py never writes perception.json: the file predates every perceive run
    try:
        return json.loads(pj.read_text()).get("final_message_source") == "cli"
    except Exception:
        return True


def write_outputs(run: Path, p: Perception):
    parts = [f"--- turn {i + 1} ---\n{t}" for i, t in enumerate(p.assistant_texts)]
    (run / "assistant_text.txt").write_text("\n\n".join(parts) + ("\n" if parts else ""))
    if _cli_final_message(run):
        cli = (run / "final_message.txt").read_text(errors="replace")
        p.final_message_source = "cli"
        p.final_message_matches_cli = cli.strip() == (p.final_message or "").strip()
        (run / "final_message.perceived.txt").write_text(p.final_message or "")
    else:
        p.final_message_source = "perceive"; p.final_message_matches_cli = None
        (run / "final_message.txt").write_text(p.final_message or "")
    (run / "perception.json").write_text(json.dumps(p.to_json(), indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True); ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    runs = Path(a.runs).resolve(); out = Path(a.out) if a.out else runs / "perception.csv"
    dirs = sorted(d for d in runs.iterdir() if (d / "manifest.json").exists())
    n = parsed = errors = 0; rows = []
    for d in dirs:
        n += 1
        try:
            p = perceive_run(d)
            write_outputs(d, p)
        except Exception as e:
            p = Perception(run_id=d.name, parse_error=f"{type(e).__name__}: {e}")
            try:
                p.body = json.loads((d / "manifest.json").read_text()).get("body", "")
            except Exception:
                pass
            (d / "perception.json").write_text(json.dumps(p.to_json() | {"traceback": traceback.format_exc()}, indent=1))
        if p.parse_error:
            errors += 1
        else:
            parsed += 1
        rows.append(p.row())
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, lineterminator="\n"); w.writeheader(); w.writerows(rows)
    print(f"perceive: {n} runs, {parsed} parsed, {errors} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
