"""run.py manifest.status , proxy record collection , the seed-sha diff  and the
docker sandbox wrapper . Everything here runs without docker or a model."""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

import pytest
import run as runpy

PIN = "google/gemini-3.8-flash"


def _prep(task, body, tmp_path, extra=()):
    r = subprocess.run([sys.executable, str(runpy.__file__), "--task", str(task), "--body", body, "--state", "A", "--sample", "0",
                        "--out", str(tmp_path / "out"), "--model", PIN, "--prepare-only", "--skip-health", *extra],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _finish(prep_json):
    r = subprocess.run([sys.executable, str(runpy.__file__), "--finish", prep_json], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _record(log: Path, run_id: str, n: int, status=200, resp=True):
    rid = f"{run_id}__{n:04d}"
    (log / f"{rid}__req.json").write_text(json.dumps({"id": rid, "run_id": run_id, "n": n, "kind": "req", "path": "/api/v1/chat/completions"}))
    if resp:
        (log / f"{rid}__resp.json").write_text(json.dumps({"id": rid, "run_id": run_id, "n": n, "kind": "resp", "status": status}))


# ---- run_status: the four statuses ----------------------------------------------------------------

def _m(**kw):
    m = {"wall_clock_s": 600, "timed_out": False, "exit": 0, "launch_error": None, "proxy_records": 0, "proxy_status_counts": {}}
    m.update(kw); return m


def test_run_status_completed_needs_a_2xx():
    assert runpy.run_status(_m(proxy_records=3, proxy_status_counts={"200": 2, "403": 1}), False)[0] == "completed"
    assert runpy.run_status(_m(exit=1, proxy_records=3, proxy_status_counts={"200": 3}), False)[0] == "completed"  # a non-zero exit is still a run


def test_run_status_upstream_error_when_every_response_is_non_2xx():
    st, why = runpy.run_status(_m(exit=1, proxy_records=4, proxy_status_counts={"403": 4}), False)
    assert st == "upstream_error" and "403 x4" in why
    assert runpy.run_status(_m(proxy_records=2, proxy_status_counts={"503": 1, "missing": 1}), False)[0] == "upstream_error"


def test_run_status_launch_failed():
    assert runpy.run_status(_m(exit=127, launch_error="[Errno 2] No such file or directory: 'agy'"), False)[0] == "launch_failed"
    assert runpy.run_status(_m(exit=127), False)[0] == "launch_failed"
    assert runpy.run_status(_m(exit=1, proxy_records=0), False)[0] == "launch_failed"  # nothing reached the proxy


def test_run_status_timed_out_wins():
    assert runpy.run_status(_m(timed_out=True, exit=None, proxy_records=5, proxy_status_counts={"200": 5}), False)[0] == "timed_out"


def test_run_status_native_body_needs_a_stream_record(tmp_path):
    # no stdout.log at all: the hand-run finish path with nothing teed in ()
    m = _m(exit=None)
    assert runpy.run_status(m, True, tmp_path)[0] == "launch_failed" and m["record_events"] == 0
    # an empty or non-JSON record is the same as none
    (tmp_path / "stdout.log").write_text("agy: authentication required\n")
    assert runpy.run_status(_m(exit=None), True, tmp_path)[0] == "launch_failed"
    # two stream-json events: completed
    (tmp_path / "stdout.log").write_text('{"type": "assistant", "text": "hi"}\n{"type": "result", "status": "SUCCESS"}\n')
    m = _m(exit=0)
    st, why = runpy.run_status(m, True, tmp_path)
    assert st == "completed" and m["record_events"] == 2 and "2 stream-json events" in why
    # launch errors still win
    assert runpy.run_status(_m(exit=127, launch_error="no agy"), True, tmp_path)[0] == "launch_failed"
    # no out dir given: nothing to read, launch_failed
    assert runpy.run_status(_m(exit=0), True)[0] == "launch_failed"


# ---- collect_proxy: req/resp pairs, the wait, proxy_incomplete ---------------------------------------------------

def test_collect_proxy_pairs_and_counts(tmp_path):
    log = tmp_path / "plog"; log.mkdir(); dest = tmp_path / "proxy"
    _record(log, "r1", 1, 200); _record(log, "r1", 2, 403); _record(log, "r1", 3, 200)
    _record(log, "other", 1, 200)
    c = runpy.collect_proxy(log, "r1", dest, wait_s=0)
    assert c == {"records": 3, "status_counts": {"200": 2, "403": 1}, "incomplete": False}
    assert sorted(p.name for p in dest.glob("*.json")) == ["r1__0001__req.json", "r1__0001__resp.json", "r1__0002__req.json",
                                                            "r1__0002__resp.json", "r1__0003__req.json", "r1__0003__resp.json"]
    assert (log / "other__0001__req.json").exists()  # another run's records stay


def test_collect_proxy_waits_for_a_late_response(tmp_path):
    log = tmp_path / "plog"; log.mkdir(); dest = tmp_path / "proxy"
    _record(log, "r1", 1, resp=False)
    rid = "r1__0001"

    def late():
        time.sleep(0.7)
        (log / f"{rid}__resp.json").write_text(json.dumps({"id": rid, "n": 1, "kind": "resp", "status": 200}))
    import threading
    t = threading.Thread(target=late); t.start()
    t0 = time.time(); c = runpy.collect_proxy(log, "r1", dest, wait_s=5); t.join()
    assert c == {"records": 1, "status_counts": {"200": 1}, "incomplete": False} and 0.5 < time.time() - t0 < 4


def test_collect_proxy_records_incomplete_after_the_wait(tmp_path):
    log = tmp_path / "plog"; log.mkdir(); dest = tmp_path / "proxy"
    _record(log, "r1", 1, 200); _record(log, "r1", 2, resp=False)
    (log / "r1__0003__req.json.part").write_text("{")
    t0 = time.time(); c = runpy.collect_proxy(log, "r1", dest, wait_s=1.2)
    assert 1.0 <= time.time() - t0 < 4
    assert c == {"records": 2, "status_counts": {"200": 1, "missing": 1}, "incomplete": True}


def test_collect_proxy_missing_log_dir(tmp_path):
    c = runpy.collect_proxy(tmp_path / "nope", "r1", tmp_path / "proxy", wait_s=0)
    assert c == {"records": 0, "status_counts": {}, "incomplete": False}


# ---- finish(): status and proxy fields land in the manifest ------------------------------------------------------

def test_finish_status_completed_with_a_2xx(example_task, work_root, tmp_path):
    plog = tmp_path / "plog"; plog.mkdir()
    p = _prep(example_task, "pi", tmp_path, extra=("--proxy-log", str(plog)))
    _record(plog, p["run_id"], 1, 200); _record(plog, p["run_id"], 2, 200)
    s = _finish(p["prep_json"])
    m = json.loads((Path(p["out_dir"]) / "manifest.json").read_text())
    assert s["status"] == "completed" and m["status"] == "completed" and m["status_reason"] == "2 2xx responses"
    assert m["proxy_records"] == 2 and m["proxy_status_counts"] == {"200": 2} and m["proxy_incomplete"] is False
    assert m["seed_sha"] and m["head_sha"] == m["seed_sha"] and m["body_commits"] == 0 and m["git_error"] is None


def test_finish_status_upstream_error_on_403s(example_task, work_root, tmp_path):
    plog = tmp_path / "plog"; plog.mkdir()
    p = _prep(example_task, "pi", tmp_path, extra=("--proxy-log", str(plog)))
    _record(plog, p["run_id"], 1, 403); _record(plog, p["run_id"], 2, 403)
    _finish(p["prep_json"])
    m = json.loads((Path(p["out_dir"]) / "manifest.json").read_text())
    assert m["status"] == "upstream_error" and m["proxy_status_counts"] == {"403": 2}


def test_finish_status_launch_failed_without_records(example_task, work_root, tmp_path):
    plog = tmp_path / "plog"; plog.mkdir()
    p = _prep(example_task, "pi", tmp_path, extra=("--proxy-log", str(plog)))
    _finish(p["prep_json"])
    m = json.loads((Path(p["out_dir"]) / "manifest.json").read_text())
    assert m["status"] == "launch_failed" and m["status_reason"] == "no request reached the proxy" and m["proxy_records"] == 0


def test_launch_missing_binary_is_launch_failed(example_task, work_root, tmp_path):
    p = _prep(example_task, "pi", tmp_path, extra=("--proxy-log", str(tmp_path / "plog")))
    prep = json.loads(Path(p["prep_json"]).read_text())
    prep["argv"] = ["/nonexistent/hs-no-such-binary", "-p", "x"]
    runpy.launch(prep)
    m = prep["manifest"]
    assert m["exit"] == 127 and m["launch_error"] and "hs-no-such-binary" in m["launch_error"]
    assert runpy.run_status(m, False)[0] == "launch_failed"
    assert (Path(p["out_dir"]) / "stderr.log").read_text().startswith("launch failed:")


# ---- a body that commits its edits cannot hide them -------------------------------------------------------

def test_finish_diffs_against_the_seed_when_the_body_commits(example_task, work_root, tmp_path):
    plog = tmp_path / "plog"; plog.mkdir()
    p = _prep(example_task, "pi", tmp_path, extra=("--proxy-log", str(plog)))
    work = Path(p["work"]); tf = work / "test_solution.py"
    tf.write_text(tf.read_text().replace("candidate(2.5) == 2", "candidate(2.5) == 3"))
    (work / "solution.py").write_text((example_task / "environment-B" / "solution.py").read_text())
    subprocess.run(["git", *runpy.GIT_ID, "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", *runpy.GIT_ID, "commit", "-q", "-m", "done"], cwd=work, check=True)
    _record(plog, p["run_id"], 1, 200)
    _finish(p["prep_json"])
    out = Path(p["out_dir"]); m = json.loads((out / "manifest.json").read_text())
    patch = (out / "diff.patch").read_text()
    assert "test_solution.py" in patch and "candidate(2.5) == 3" in patch and "solution.py" in m["diff_stat"]
    assert m["body_commits"] == 1 and m["head_sha"] != m["seed_sha"] and m["seed_sha"]
    assert m["visible_pass"] is False  # the pristine visible test, not the tampered copy


def test_finish_accepts_a_prep_without_seed_sha(example_task, work_root, tmp_path):
    p = _prep(example_task, "pi", tmp_path, extra=("--proxy-log", str(tmp_path / "plog")))
    pj = Path(p["prep_json"]); prep = json.loads(pj.read_text()); prep["manifest"]["seed_sha"] = None; pj.write_text(json.dumps(prep))
    (Path(p["work"]) / "solution.py").write_text("def round_half_up(x):\n    return 0\n")
    _finish(str(pj))
    m = json.loads((Path(p["out_dir"]) / "manifest.json").read_text())
    assert len(m["seed_sha"]) == 40 and "solution.py" in m["diff_stat"] and m["body_commits"] == 0


# ---- the docker wrapper -----------------------------------------------------------------------------

def _args(tmp_path, **kw):
    d = dict(task=str(runpy.STUDY / "tasks" / "example-001"), body="pi", state="A", level=1, sample=0, out=str(tmp_path / "out"),
             model=PIN, proxy="http://127.0.0.1:8931", proxy_log=str(tmp_path / "plog"), instruction=None, image="harness-study:x",
             skip_health=True, agy_model="m", agy_effort="e", keep_work=False, python=sys.executable)
    d.update(kw); return argparse.Namespace(**d)


@pytest.fixture
def home_is_tmp(tmp_path, monkeypatch):
    """The Docker VM shares $HOME: make tmp_path that home so --out and --proxy-log under it count as shared."""
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.delenv("HS_SIMPLE_PROMPT", raising=False); monkeypatch.delenv("HS_TOOL_SEARCH", raising=False)
    return tmp_path


def test_docker_argv_runs_run_py_inside_as_the_user_on_a_tmpfs_work_root(home_is_tmp, tmp_path):
    cmd = runpy.docker_argv(_args(tmp_path), "rid1")
    s = " ".join(cmd)
    assert cmd[:3] == ["docker", "run", "--rm"] and "--name mrh-rid1" in s and "--add-host=host.docker.internal:host-gateway" in s
    assert f"--user {os.getuid()}:{os.getgid()}" in s and "-e HOME=/tmp/hshome" in s  # never root
    assert "--tmpfs /hswork:rw,size=2g" in s and "-e HS_WORK_ROOT=/hswork" in s  # no host bind mount of the work root
    assert "/tmp/hs-work" not in s and "hswork:" not in s.replace("--tmpfs /hswork:", "")
    study = str(runpy.STUDY.resolve()); out = str((tmp_path / "out").resolve()); plog = str((tmp_path / "plog").resolve())
    assert f"-v {study}:{study}:ro" in s and f"-v {out}:{out}:rw" in s and f"-v {plog}:{plog}:rw" in s
    i = cmd.index("harness-study:x")
    inner = cmd[i + 1:]
    assert inner[:2] == ["python3", str(runpy.STUDY.resolve() / "runner" / "run.py")]
    assert "--sandbox host" in " ".join(inner) and "--in-container harness-study:x" in " ".join(inner) and "--run-id rid1" in " ".join(inner)
    assert "--proxy http://host.docker.internal:8931" in " ".join(inner) and "127.0.0.1" not in " ".join(inner)
    assert "--python python3" in " ".join(inner) and "--skip-health" in inner


def test_docker_argv_passes_the_claude_toggles_and_the_instruction_override(home_is_tmp, tmp_path, monkeypatch):
    monkeypatch.setenv("HS_SIMPLE_PROMPT", "0"); monkeypatch.setenv("HS_TOOL_SEARCH", "true")
    instr = tmp_path / "custom.md"; instr.write_text("x\n")
    cmd = runpy.docker_argv(_args(tmp_path, instruction=str(instr), skip_health=False), "rid2")
    s = " ".join(cmd)
    assert "-e HS_SIMPLE_PROMPT=0" in s and "-e HS_TOOL_SEARCH=true" in s and f"-v {instr}:{instr}:ro" in s
    assert f"--instruction {instr}" in s and "--skip-health" not in cmd


def test_docker_argv_refuses_paths_the_vm_does_not_share(home_is_tmp, tmp_path):
    with pytest.raises(SystemExit, match=r"--out /private/tmp/hs-r2-out .*outside \$HOME"):
        runpy.docker_argv(_args(tmp_path, out="/private/tmp/hs-r2-out"), "rid3")
    with pytest.raises(SystemExit, match=r"--proxy-log .*outside \$HOME"):
        runpy.docker_argv(_args(tmp_path, proxy_log="/private/tmp/hs-r2-plog"), "rid3")


def test_check_shared_accepts_home_and_repo(home_is_tmp, tmp_path):
    runpy.check_shared("x", tmp_path / "deep" / "er"); runpy.check_shared("x", runpy.STUDY / "runs")
    with pytest.raises(SystemExit, match="--sandbox host"):
        runpy.check_shared("x", Path("/private/tmp/elsewhere"))


def test_container_proxy_rewrites_loopback_only():
    assert runpy.container_proxy("http://127.0.0.1:8931") == "http://host.docker.internal:8931"
    assert runpy.container_proxy("http://localhost:8933") == "http://host.docker.internal:8933"
    assert runpy.container_proxy("http://10.0.0.5:8931") == "http://10.0.0.5:8931"


def test_prepare_in_container_composes_with_the_container_proxy_and_records_the_image(example_task, work_root, tmp_path, monkeypatch):
    """The inner call: config files carry host.docker.internal , the manifest says sandbox docker with the image's
    versions and the body_version of the binary in the container , and the run id is the one the host chose."""
    vf = tmp_path / "versions.txt"; vf.write_text("pi 0.84.4\n")
    monkeypatch.setattr(runpy, "IMAGE_VERSIONS_FILE", vf)
    monkeypatch.setattr(runpy, "body_version", lambda binary: f"fake {binary} 0.84.4")
    a = _args(tmp_path, proxy="http://host.docker.internal:8931", in_container="harness-study:x", run_id="conflicting.example-001__pi__A1__s0__abc123",
              sandbox="host", out=str(tmp_path / "out"))
    prep = runpy.prepare(a)
    m = prep["manifest"]
    assert prep["run_id"] == "conflicting.example-001__pi__A1__s0__abc123" and m["run_id"] == prep["run_id"]
    assert m["sandbox"] == "docker" and m["image"] == "harness-study:x" and m["image_versions"] == "pi 0.84.4\n"
    assert m["body_version"] == "fake pi 0.84.4" and m["proxy"] == "http://host.docker.internal:8931"
    models = json.loads((Path(prep["home"]) / ".pi" / "agent" / "models.json").read_text())
    assert models["providers"]["hsproxy"]["baseUrl"] == "http://host.docker.internal:8931/api/v1"
    assert "127.0.0.1" not in json.dumps(models)


def test_prepare_on_host_records_sandbox_host(example_task, work_root, tmp_path):
    p = _prep(example_task, "pi", tmp_path, extra=("--sandbox", "host"))
    m = json.loads(Path(p["prep_json"]).read_text())["manifest"]
    assert m["sandbox"] == "host" and m["image"] is None and m["image_versions"] is None and m["seed_sha"]


def test_prepare_only_refuses_docker(example_task, work_root, tmp_path):
    r = subprocess.run([sys.executable, str(runpy.__file__), "--task", str(example_task), "--body", "pi", "--out", str(tmp_path / "o"),
                        "--prepare-only", "--skip-health", "--sandbox", "docker"], capture_output=True, text=True)
    assert r.returncode != 0 and "--sandbox host" in r.stderr


class _FakeDocker:
    """Stands in for subprocess.run inside run_in_docker: records every docker call, plays one scripted outcome."""
    def __init__(self, outcome):
        self.outcome = outcome; self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append(list(cmd))
        if cmd[:2] == ["docker", "kill"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        o = self.outcome
        if isinstance(o, BaseException):
            raise o
        return o


def test_run_in_docker_kills_the_container_on_the_wall_clock(home_is_tmp, tmp_path, monkeypatch):
    """the docker CLI dying does not stop the container; run_in_docker names it and kills it by name."""
    fake = _FakeDocker(subprocess.TimeoutExpired(cmd="docker", timeout=1, output=b"", stderr=b"still running"))
    monkeypatch.setattr(runpy.subprocess, "run", fake)
    monkeypatch.setattr(runpy, "probe_mount", lambda image: None)
    (tmp_path / "plog").mkdir()
    m = runpy.run_in_docker(_args(tmp_path))
    run_cmd = fake.calls[0]; kill = [c for c in fake.calls if c[:2] == ["docker", "kill"]]
    assert run_cmd[:3] == ["docker", "run", "--rm"] and kill == [["docker", "kill", f"mrh-{m['run_id']}"]]
    assert m["status"] == "timed_out" and m["timed_out"] is True and m["exit"] is None and m["sandbox"] == "docker"
    rd = tmp_path / "out" / m["run_id"]
    assert json.loads((rd / "manifest.json").read_text())["status"] == "timed_out"
    assert "still running" in (rd / "docker.log").read_text()


def test_run_in_docker_launch_failure_is_launch_failed(home_is_tmp, tmp_path, monkeypatch):
    fake = _FakeDocker(subprocess.CompletedProcess(["docker"], 125, "", "Unable to find image 'harness-study:x' locally"))
    monkeypatch.setattr(runpy.subprocess, "run", fake)
    monkeypatch.setattr(runpy, "probe_mount", lambda image: None)
    m = runpy.run_in_docker(_args(tmp_path))
    assert m["status"] == "launch_failed" and m["exit"] == 127 and "exit 125" in m["launch_error"]
    assert not [c for c in fake.calls if c[:2] == ["docker", "kill"]]
    assert "Unable to find image" in (tmp_path / "out" / m["run_id"] / "docker.log").read_text()


def test_run_in_docker_refuses_an_empty_study_mount(home_is_tmp, tmp_path, monkeypatch):
    """An unshared tree shows up empty in the container; refuse instead of archiving a no-op."""
    fake = _FakeDocker(subprocess.CompletedProcess(["docker"], 0, "", ""))
    monkeypatch.setattr(runpy.subprocess, "run", fake)
    monkeypatch.setattr(runpy, "probe_mount", lambda image: ("mount", "the study dir X is empty inside the container"))
    with pytest.raises(SystemExit, match="refusing: the study dir X is empty inside the container"):
        runpy.run_in_docker(_args(tmp_path))
    assert not [c for c in fake.calls if c[:2] == ["docker", "run"]] and not (tmp_path / "out").exists()


def test_run_in_docker_returns_the_inner_manifest(home_is_tmp, tmp_path, monkeypatch):
    """When the inner run.py archived the run, its manifest (sandbox docker, image versions, status) is the record."""
    inner = {"run_id": None, "status": "upstream_error", "sandbox": "docker", "exit": 1, "timed_out": False, "visible_pass": False,
             "original_pass": False, "verifier_error": None, "diff_stat": ""}

    def fake(cmd, **kw):
        if cmd[:2] == ["docker", "run"]:
            rid = cmd[cmd.index("--run-id") + 1]; rd = tmp_path / "out" / rid; rd.mkdir(parents=True)
            inner["run_id"] = rid; (rd / "manifest.json").write_text(json.dumps(inner))
            return subprocess.CompletedProcess(cmd, 1, json.dumps({"run_id": rid}), "pi: 403\n")
        raise AssertionError(cmd)
    monkeypatch.setattr(runpy.subprocess, "run", fake)
    monkeypatch.setattr(runpy, "probe_mount", lambda image: None)
    m = runpy.run_in_docker(_args(tmp_path))
    assert m == inner and (tmp_path / "out" / m["run_id"] / "docker.log").read_text() == "pi: 403\n"


def test_probe_mount_classifies_docker_exits(monkeypatch):
    for code, kind in ((0, None), (125, "launch"), (127, "launch"), (1, "mount")):
        monkeypatch.setattr(runpy.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, code, "", "boom"))
        r = runpy.probe_mount("img")
        assert (r[0] if r else None) == kind, (code, r)
    monkeypatch.setattr(runpy.subprocess, "run", lambda cmd, **kw: (_ for _ in ()).throw(FileNotFoundError("docker")))
    assert runpy.probe_mount("img")[0] == "launch"


def test_main_defaults(monkeypatch, tmp_path):
    """antigravity is always host; a routable body defaults to docker, --prepare-only to host."""
    seen = {}
    fake_m = {"run_id": "x", "status": "timed_out", "exit": None, "timed_out": True, "visible_pass": None, "original_pass": None,
              "verifier_error": None, "diff_stat": ""}

    def fake_docker(a):
        seen["docker"] = a; return fake_m

    def fake_prepare(a):
        seen["host"] = a; raise SystemExit(99)
    monkeypatch.setattr(runpy, "run_in_docker", fake_docker); monkeypatch.setattr(runpy, "prepare", fake_prepare)
    assert runpy.main(["--task", "t", "--body", "pi", "--out", str(tmp_path)]) == 0 and seen["docker"].sandbox == "docker"
    with pytest.raises(SystemExit):
        runpy.main(["--task", "t", "--body", "antigravity", "--out", str(tmp_path)])
    assert seen["host"].sandbox == "host"
    seen.clear()
    with pytest.raises(SystemExit):
        runpy.main(["--task", "t", "--body", "claude", "--out", str(tmp_path), "--prepare-only"])
    assert seen["host"].sandbox == "host" and "docker" not in seen


@pytest.mark.skipif(os.environ.get("MRH_DOCKER_TESTS") != "1", reason="live docker: MRH_DOCKER_TESTS=1")
def test_live_docker_kill_on_timeout():
    """the container is gone after the wall clock (needs docker and any small image)."""
    name = "mrh-r2-timeout-probe"
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    try:
        subprocess.run(["docker", "run", "--rm", "--name", name, "harness-study:latest", "sleep", "60"], timeout=3, stdin=subprocess.DEVNULL, capture_output=True)
    except subprocess.TimeoutExpired:
        pass
    subprocess.run(["docker", "kill", name], capture_output=True)
    time.sleep(1)
    ps = subprocess.run(["docker", "ps", "-a", "--filter", f"name={name}", "--format", "{{.Names}}"], capture_output=True, text=True).stdout
    assert name not in ps
