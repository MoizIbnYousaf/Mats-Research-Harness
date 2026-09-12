"""batch.py --dry-run cell counts, twin rule, --max-runs guard, --resume (only `completed` counts), argparse choices
and the consecutive-dead-cell abort."""
import json, shutil, subprocess

import pytest
import batch


def _tasks(example_task, twin_task, tmp_path):
    root = tmp_path / "tasks"; root.mkdir()
    shutil.copytree(example_task, root / "t1"); shutil.copytree(example_task, root / "t2"); shutil.copytree(twin_task, root / "t1-twin")
    (root / "t2" / "task.toml").write_text((root / "t2" / "task.toml").read_text().replace('id = "example-001"', 'id = "example-002"'))
    return root


def test_dry_run_count(example_task, twin_task, tmp_path, capsys):
    root = _tasks(example_task, twin_task, tmp_path)
    batch.main(["--tasks", str(root), "--bodies", "claude", "pi", "--states", "A", "B", "--samples", "3", "--dry-run", "--out", str(tmp_path / "o")])
    out = capsys.readouterr().out.strip().splitlines()
    cells = [json.loads(l) for l in out[:-1]]
    assert len(cells) == 26 and out[-1].startswith("batch: 26 cells")
    twins = [c for c in cells if c["kind"] == "twin"]
    assert len(twins) == 2 and all(c["state"] == "A" and c["sample"] == 0 for c in twins)
    assert not (tmp_path / "o").exists()


def test_seed_is_deterministic(example_task, twin_task, tmp_path, capsys):
    root = _tasks(example_task, twin_task, tmp_path)
    args = ["--tasks", str(root), "--bodies", "claude", "pi", "--samples", "2", "--dry-run", "--seed", "7"]
    batch.main(args); a = capsys.readouterr().out
    batch.main(args); b = capsys.readouterr().out
    assert a == b


def test_max_runs_refuses(example_task, twin_task, tmp_path, capsys):
    root = _tasks(example_task, twin_task, tmp_path)
    with pytest.raises(SystemExit, match="7 cells exceed --max-runs 2"):
        batch.main(["--tasks", str(root), "--bodies", "pi", "--samples", "3", "--max-runs", "2", "--out", str(tmp_path / "o")])
    assert not (tmp_path / "o").exists()  # refused before order.jsonl
    # --dry-run still prints the whole plan so the cap can be sized 
    assert batch.main(["--tasks", str(root), "--bodies", "pi", "--samples", "3", "--max-runs", "2", "--dry-run", "--out", str(tmp_path / "o")]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 8 and out[-1].startswith("batch: 7 cells") and out[-1].endswith("exceeds --max-runs 2, a real batch refuses")


def test_resume_skips_only_completed_cells(example_task, twin_task, tmp_path, capsys):
    root = _tasks(example_task, twin_task, tmp_path); out = tmp_path / "o"
    key = {"split": "conflicting", "task_id": "example-001", "body": "pi", "state": "A", "level": 1}
    (out / "dead").mkdir(parents=True); (out / "done").mkdir(); (out / "old").mkdir()
    (out / "dead" / "manifest.json").write_text(json.dumps({**key, "sample": 0, "status": "upstream_error"}))
    (out / "old" / "manifest.json").write_text(json.dumps({**key, "sample": 1}))  # no status: a pre-contract manifest, redone
    args = ["--tasks", str(root / "t1"), "--bodies", "pi", "--samples", "2", "--dry-run", "--resume", "--out", str(out)]
    batch.main(args)
    assert capsys.readouterr().out.strip().splitlines()[-1].startswith("batch: 2 cells")
    (out / "done" / "manifest.json").write_text(json.dumps({**key, "sample": 0, "status": "completed"}))
    batch.main(args)
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1].startswith("batch: 1 cells") and json.loads(lines[0])["sample"] == 1


@pytest.mark.parametrize("bad", [["--level", "4"], ["--sandbox", "bogus"], ["--bodies", "agy"], ["--states", "C"]])
def test_rejects_values_run_py_rejects(example_task, twin_task, tmp_path, capsys, bad):
    root = _tasks(example_task, twin_task, tmp_path)
    argv = ["--tasks", str(root), "--bodies", "pi", "--dry-run", "--out", str(tmp_path / "o")]
    if bad[0] == "--bodies":
        argv = ["--tasks", str(root), "--dry-run", "--out", str(tmp_path / "o")]
    with pytest.raises(SystemExit) as e:
        batch.main(argv + bad)
    assert e.value.code == 2 and "invalid choice" in capsys.readouterr().err and not (tmp_path / "o").exists()


def test_accepts_every_run_py_value(example_task, twin_task, tmp_path, capsys):
    root = _tasks(example_task, twin_task, tmp_path)
    assert batch.main(["--tasks", str(root), "--bodies", "antigravity", "claude", "codex", "opencode", "pi", "--level", "3", "--sandbox", "host",
                       "--states", "A", "B", "fixable", "--dry-run", "--out", str(tmp_path / "o")]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1].startswith("batch: 95 cells (3 tasks x 5 bodies x states A,B,fixable x 3 samples; twins A x 1)")


def _fake_run(status_by_call, calls):
    """Stand-in for subprocess.run: run.py's summary line with the scripted status (or a crash when status is None)."""
    def run(cmd, **kw):
        calls.append(cmd); st = status_by_call(len(calls))
        if st is None:
            return subprocess.CompletedProcess(cmd, 1, "", "refusing: something\n")
        rid = cmd[cmd.index("--task") + 1].rsplit("/", 1)[-1]
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"run_id": rid, "status": st, "exit": 1}) + "\n", "")
    return run


def test_aborts_after_consecutive_dead_cells(example_task, twin_task, tmp_path, capsys, monkeypatch):
    root = _tasks(example_task, twin_task, tmp_path); out = tmp_path / "o"; calls = []
    monkeypatch.setattr(batch.subprocess, "run", _fake_run(lambda n: "upstream_error" if n % 2 else None, calls))
    rc = batch.main(["--tasks", str(root), "--bodies", "pi", "--samples", "3", "--concurrency", "1", "--out", str(out)])
    err = capsys.readouterr()
    assert rc == 2 and len(calls) == batch.DEAD_ABORT and "aborted after 5 consecutive cells" in err.err
    lines = err.out.strip().splitlines()
    assert len(lines) == 7 and sum("batch aborted" in l for l in lines) == 2
    assert (out / "order.jsonl").read_text().count("\n") == 7 and "exit 1" in (out / "batch-errors.log").read_text()
    for c in calls:  # every cell is one run.py call carrying the cell, never a --sandbox unless asked
        assert c[1].endswith("run.py") and "--sandbox" not in c


def test_a_completed_cell_resets_the_dead_count(example_task, twin_task, tmp_path, capsys, monkeypatch):
    root = _tasks(example_task, twin_task, tmp_path); calls = []
    monkeypatch.setattr(batch.subprocess, "run", _fake_run(lambda n: "completed" if n % 4 == 0 else "launch_failed", calls))
    rc = batch.main(["--tasks", str(root), "--bodies", "pi", "--samples", "3", "--concurrency", "1", "--sandbox", "host", "--out", str(tmp_path / "o")])
    assert rc == 0 and len(calls) == 7 and all("--sandbox" in c and c[c.index("--sandbox") + 1] == "host" for c in calls)
    assert sum('"status": "completed"' in l for l in capsys.readouterr().out.splitlines()) == 1


def test_missing_environment_dir_is_skipped_and_counted(example_task, twin_task, tmp_path, capsys):
    root = _tasks(example_task, twin_task, tmp_path)
    shutil.rmtree(root / "t2" / "environment-B"); shutil.rmtree(root / "t2" / "environment-fixable")
    batch.main(["--tasks", str(root), "--bodies", "pi", "--states", "A", "B", "fixable", "--samples", "1", "--dry-run", "--out", str(tmp_path / "o")])
    out = capsys.readouterr().out.strip().splitlines()
    cells = [json.loads(l) for l in out[:-1]]
    assert len(cells) == 5 and not [c for c in cells if c["task_id"] == "example-002" and c["state"] != "A"]
    assert out[-1].startswith("batch: 5 cells") and out[-1].endswith("2 skipped (missing environment dir or duplicate task dir): example-002:B example-002:fixable")


def test_shared_twin_runs_once(example_task, twin_task, tmp_path, capsys):
    root = _tasks(example_task, twin_task, tmp_path); shutil.copytree(twin_task, root / "again-twin")
    batch.main(["--tasks", str(root), "--bodies", "pi", "--samples", "1", "--dry-run", "--out", str(tmp_path / "o")])
    out = capsys.readouterr().out.strip().splitlines()
    twins = [json.loads(l) for l in out[:-1] if json.loads(l)["kind"] == "twin"]
    assert len(twins) == 1 and "1 skipped" in out[-1] and out[-1].endswith("example-001-twin")
