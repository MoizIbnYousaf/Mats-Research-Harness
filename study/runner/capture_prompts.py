#!/usr/bin/env python3
"""Capture the wire prompts of the four routable bodies from archived runs (PLAN v3 line 26: "wire prompts for the
four routable bodies re-captured on the Gemini slug and hashed"; line 33: the Claude Code hash "computed after
normalising its per-run memory path"; hand-work ledger row "capture, hash and section the four wire prompts";
Verification 6). Antigravity has no capturable wire prompt and is printed as such.

capture_prompts.py --runs DIR... [--out study/prompts] [--force]
For each run dir (manifest.json + proxy/*.json) whose body is claude, codex, opencode or pi, the first agent record
(request.tools non-empty) carries the prompt: request.system (/messages), request.instructions (/responses) or the
first system message (/chat/completions). The run's work root (manifest.work_root, with and without the /private
prefix, plain and dash-encoded as Claude Code writes it into its memory path) and the run id are replaced by fixed
tokens before hashing. Writes <out>/<body>.gemini.txt, <out>/<body>.gemini.meta.json (model, run id, record, tool
count, sha256, what was normalised) and <out>/SHA256SUMS over every *.gemini.txt (`shasum -a 256 -c SHA256SUMS`
checks it). The first run found per body wins; an existing capture is kept unless --force. PREDICTIONS.md is written
by hand afterwards (figures.py names its two lines); verify.py reports both files.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path

STUDY = Path(__file__).resolve().parent.parent
ROUTABLE = ("claude", "codex", "opencode", "pi")


def _text(c) -> str:
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in c)
    return "" if c is None else str(c)


def prompt_of(rec: dict) -> tuple[str, str] | None:
    """(prompt text, where it came from) for an agent record, else None."""
    req = rec.get("request") or {}
    if not req.get("tools"):
        return None
    if req.get("system") is not None:
        return _text(req["system"]), "request.system"
    if req.get("instructions") is not None:
        return _text(req["instructions"]), "request.instructions"
    for m in req.get("messages") or []:
        if isinstance(m, dict) and m.get("role") == "system":
            return _text(m.get("content")), "first system message"
    return None


def normalise(text: str, manifest: dict) -> tuple[str, list[str]]:
    """Replace the run's work root (plain, /private-prefixed, dash-encoded) and run id by fixed tokens."""
    forms: list[tuple[str, str]] = []
    wroot = manifest.get("work_root") or ""
    if wroot:
        alt = wroot[len("/private"):] if wroot.startswith("/private/") else "/private" + wroot
        for w in (wroot, alt):
            forms.append((w, "<WORK_ROOT>")); forms.append((w.replace("/", "-"), "<WORK_ROOT_DASHED>"))
    if manifest.get("run_id"):
        forms.append((manifest["run_id"], "<RUN_ID>"))
    subs = []
    for old, new in sorted(forms, key=lambda f: -len(f[0])):
        if old and old in text:
            text = text.replace(old, new); subs.append(f"{old} -> {new}")
    return text, subs


def capture(runs: list[Path], out: Path, force: bool = False) -> dict:
    out.mkdir(parents=True, exist_ok=True); done: dict[str, str] = {}
    manifests = []
    for root in runs:
        root = Path(root).resolve()
        manifests += [root / "manifest.json"] if (root / "manifest.json").exists() else sorted(root.glob("*/manifest.json"))
    for mf in manifests:
        m = json.loads(mf.read_text()); body = m.get("body")
        if body not in ROUTABLE or body in done:
            continue
        txt = out / f"{body}.gemini.txt"
        if txt.exists() and not force:
            done[body] = f"kept {txt.name} (use --force to recapture)"; continue
        for rf in sorted((mf.parent / "proxy").glob("*.json")):
            rec = json.loads(rf.read_text()); got = prompt_of(rec)
            if got:
                break
        else:
            continue
        text, subs = normalise(got[0], m)
        txt.write_text(text); sha = hashlib.sha256(text.encode()).hexdigest()
        meta = {"harness": body, "model_pinned": m.get("model"), "run_id": m.get("run_id"),
                "captured": f"{time.strftime('%Y-%m-%d')} via runner/capture_prompts.py from {mf.parent.name}/proxy/{rf.name}: {got[1]} of {rec.get('path')}",
                "chars": len(text), "sha256": sha, "tools": len(rec["request"]["tools"]), "normalised": subs}
        (out / f"{body}.gemini.meta.json").write_text(json.dumps(meta, indent=1) + "\n")
        done[body] = f"wrote {txt.name} sha256={sha[:16]}.. tools={meta['tools']} normalised={len(subs)}"
    files = sorted(out.glob("*.gemini.txt"))
    if files:
        (out / "SHA256SUMS").write_text("".join(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}\n" for f in files))
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", nargs="+", required=True); ap.add_argument("--out", default=str(STUDY / "prompts"))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    done = capture([Path(r) for r in a.runs], Path(a.out).resolve(), a.force)
    for b in ROUTABLE:
        print(f"{b}: {done.get(b, 'no run with an agent proxy record found')}")
    print("antigravity: wire prompt not capturable (native body, no proxy record)")
    print(f"SHA256SUMS: {Path(a.out).resolve() / 'SHA256SUMS'} ({len(done)} of {len(ROUTABLE)} bodies)")
    return 0 if len([b for b in ROUTABLE if b in done]) == len(ROUTABLE) else 1


if __name__ == "__main__":
    sys.exit(main())
