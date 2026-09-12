"""capture_prompts.py on the fixture runs: one prompt per routable body from the first agent record, SHA256SUMS,
and the work-root / run-id normalisation (Verification 6)."""
import hashlib, json

import capture_prompts


def test_capture_fixture_runs(runs_copy, tmp_path):
    out = tmp_path / "prompts"
    done = capture_prompts.capture([runs_copy], out)
    assert set(done) == {"claude", "codex", "pi"}  # no opencode fixture run; antigravity never captured
    assert (out / "claude.gemini.txt").read_text() == "You are Claude Code."
    assert (out / "codex.gemini.txt").read_text() == "You are Codex."
    assert (out / "pi.gemini.txt").read_text() == "You are pi."  # the housekeeping title call is skipped
    sums = dict(reversed(l.split("  ")) for l in (out / "SHA256SUMS").read_text().splitlines())
    assert set(sums) == {"claude.gemini.txt", "codex.gemini.txt", "pi.gemini.txt"}
    assert sums["pi.gemini.txt"] == hashlib.sha256(b"You are pi.").hexdigest()
    meta = json.loads((out / "codex.gemini.meta.json").read_text())
    assert meta["model_pinned"] == "google/gemini-3.8-flash" and meta["tools"] == 2 and "request.instructions" in meta["captured"]
    assert capture_prompts.main(["--runs", str(runs_copy), "--out", str(out)]) == 1  # opencode still missing
    assert capture_prompts.capture([runs_copy], out)["claude"].startswith("kept")


def test_normalises_work_root_and_run_id(tmp_path):
    run = tmp_path / "runs" / "conflicting.t__claude__A1__s0__abc123"; (run / "proxy").mkdir(parents=True)
    rid = "conflicting.t__claude__A1__s0__abc123"; wroot = f"/tmp/hs-work/{rid}"
    (run / "manifest.json").write_text(json.dumps({"run_id": rid, "body": "claude", "model": "google/gemini-3.8-flash", "work_root": wroot}))
    sys_text = (f"Memory at `/private{wroot}/home/.claude/projects/-private-tmp-hs-work-{rid}-work/memory/`.\n"
                f"Primary working directory: {wroot}/work")
    (run / "proxy" / f"{rid}__1.json").write_text(json.dumps({"path": "/api/v1/messages", "request": {"system": [{"type": "text", "text": sys_text}], "tools": [{}]}}))
    done = capture_prompts.capture([tmp_path / "runs"], tmp_path / "out")
    text = (tmp_path / "out" / "claude.gemini.txt").read_text()
    assert "claude" in done and rid not in text and "hs-work" not in text
    assert text == ("Memory at `<WORK_ROOT>/home/.claude/projects/<WORK_ROOT_DASHED>-work/memory/`.\n"
                    "Primary working directory: <WORK_ROOT>/work")
    assert len(json.loads((tmp_path / "out" / "claude.gemini.meta.json").read_text())["normalised"]) == 3
