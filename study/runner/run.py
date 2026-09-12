#!/usr/bin/env python3
"""One run: (task, body, state, level, sample) -> archived run dir (PLAN v3 lines 27-29, 33, 35).

run.py --task DIR --body B [--state A|B|fixable] [--level 1|2|3] [--sample N] [--out DIR] [--model SLUG]
       [--sandbox docker|host] [--proxy URL] [--instruction FILE] [--prepare-only | --finish PREP.json] [--keep-work]

Flow: task.toml -> env dir for the state -> fresh work dir under HS_WORK_ROOT (outside any instruction tree; refused
otherwise) -> README.md + prompt.md rendered from the instruction level -> git seed commit (its sha is recorded and is
what finish() diffs against, so a body that commits cannot hide its edits) -> per-run token `hs_<run_id>` ->
harness_env.compose with the proxy URL the body will actually use -> (proxy /health unless native) -> launch with a
600 s wall clock -> finish(): diff.patch against the seed, work_final/, the two reruns, proxy records moved in
(waits up to 15 s for records still being written), manifest.json with `status`.

manifest.status: `completed` (the body exited on its own and at least one proxied response was HTTP 2xx, or the body
is native and its stream-json record holds at least one event), `launch_failed` (binary missing, exec error, no request
ever reached the proxy, or a native run with no record), `timed_out` (wall clock hit), `upstream_error` (every proxied response was non-2xx, e.g. the 403 of an
exhausted key). The scorer treats everything but `completed` as invalid. `proxy_status_counts` is the HTTP status
distribution of the run's proxied responses; `proxy_incomplete` is true when a record was still missing after the wait.

--sandbox docker (the default for the four routable bodies) runs this script INSIDE the study image: the study dir,
the task dir and the instruction file are bind-mounted read-only at their host paths, --out and --proxy-log
read-write, the work root is a tmpfs (/hswork; HS_WORK_ROOT on the host is ignored), HOME is a writable tmpfs path,
the container runs as the invoking uid:gid (Claude Code refuses --dangerously-skip-permissions as root), the proxy is
reached as http://host.docker.internal:<port>, and every per-body config file is composed with that URL inside the
container. The container is named mrh-<run_id> and killed with `docker kill` if it outlives the wall clock plus the
finish() grace. Every bind-mounted path must lie under $HOME or the repository (colima shares only $HOME with the VM);
anything else is refused before the run. --sandbox host runs the CLI on this machine (hand runs, `mrh watch`);
Antigravity always runs on the host. --prepare-only stops before the launch and prints the prep JSON (host only);
--finish PREP.json archives such a run afterwards.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time, tomllib, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_env import BODIES, AGY_MODEL_DEFAULT, AGY_EFFORT_DEFAULT, compose  # noqa: E402
from rerun import ENV_DIRS, format_log, reruns  # noqa: E402

STUDY = Path(__file__).resolve().parent.parent
MODEL_DEFAULT = "deepseek/deepseek-v4-flash-0731"
MAX_TURNS = 25
WALL_CLOCK_S = 600
FINISH_GRACE_S = 420  # docker: what the inner run.py may spend in finish() after the wall clock (two 180 s reruns, copies)
PROXY_WAIT_S = 15  # finish(): wait for proxy records still being written
STATES = ("A", "B", "fixable")
STATUSES = ("completed", "launch_failed", "timed_out", "upstream_error")
INSTRUCTION_MARKERS = ("CLAUDE.md", "AGENTS.md", "GEMINI.md", ".claude", ".gemini", ".codex", ".opencode", ".pi")
HOME_INSTRUCTION_FILES = ("~/.gemini/GEMINI.md", "~/GEMINI.md", "~/AGENTS.md", "~/CLAUDE.md")
GIT_ID = ["-c", "user.name=study", "-c", "user.email=study@localhost"]
DOCKER_HOST = "host.docker.internal"
DOCKER_DNS_SINK = "127.0.0.1"  # nothing listens there in the container, so every hostname lookup fails; host.docker.internal is in /etc/hosts
CONTAINER_HOME = "/tmp/hshome"
CONTAINER_WORK_ROOT = "/hswork"
DOCKER_LAUNCH_EXITS = (125, 126, 127)  # docker CLI: daemon/image error, command not executable, command not found
IMAGE_VERSIONS_FILE = Path("/versions.txt")  # written by the Dockerfile: the CLI versions baked into the image


def sha(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()[:16]


def default_proxy() -> str:
    return f"http://127.0.0.1:{os.environ.get('HS_PROXY_PORT') or 8931}"


def container_proxy(proxy: str) -> str:
    """The URL the body reaches the host proxy at from inside the container."""
    return proxy.replace("127.0.0.1", DOCKER_HOST).replace("localhost", DOCKER_HOST)


def read_task(task: Path) -> dict:
    t = tomllib.loads((task / "task.toml").read_text())["task"]
    return {"task_id": t["id"], "kind": t.get("kind", "impossible"), "split": t.get("split", ""),
            "entry_point": t.get("entry_point", ""), "twin_of": t.get("twin_of", "") or ""}


def make_run_id(t: dict, a) -> str:
    return f"{t['split'] or 'na'}.{t['task_id']}__{a.body}__{a.state}{a.level}__s{a.sample}__{uuid.uuid4().hex[:6]}"


def instruction_file(state: str, level: int, override: str | None) -> Path:
    if override:
        return Path(override).resolve()
    d = STUDY / "prompts" / "instructions"
    return d / ("state_b.md" if state in ("B", "fixable") else f"level{level}.md")


def check_ancestors(wroot: Path):
    for anc in [wroot] + list(wroot.parents):
        for nm in INSTRUCTION_MARKERS:
            if (anc / nm).exists():
                raise SystemExit(f"refusing: {anc / nm} would be read by the body from an ancestor of the work dir "
                                 f"(set HS_WORK_ROOT to a clean root)")


def home_instruction_files() -> list[str]:
    return [p for p in HOME_INSTRUCTION_FILES if Path(os.path.expanduser(p)).exists()]


def body_version(binary: str) -> str | None:
    try:
        r = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=20)
        line = (r.stdout or r.stderr).strip().splitlines()
        return line[0] if line else None
    except Exception:
        return None


def git(work: Path, *args, check=True, capture=False):
    return subprocess.run(["git", *GIT_ID, *args], cwd=work, check=check, capture_output=capture, text=True)


def base_manifest(t: dict, task: Path, run_id: str, a, sandbox: str, image: str | None) -> dict:
    """The fields every manifest carries, filled before the launch (the docker shell manifest uses the same set)."""
    return {"run_id": run_id, "task_path": str(task), "task_id": t["task_id"], "split": t["split"], "kind": t["kind"],
            "twin_of": t["twin_of"], "entry_point": t["entry_point"], "body": a.body, "state": a.state, "level": a.level,
            "sample": a.sample, "model": None, "agy_model": None, "agy_effort": None, "cmd": None, "env_names": None,
            "proxy": None, "sandbox": sandbox, "image": image,
            "instruction_file": None, "instruction_sha": None, "readme_sha": None, "simple_prompt": None, "tool_search": None,
            "body_version": None, "image_versions": None, "max_turns": None, "wall_clock_s": WALL_CLOCK_S, "seed_sha": None,
            "started": None, "ended": None, "exit": None, "timed_out": None, "launch_error": None, "status": None,
            "status_reason": None, "diff_stat": None, "body_commits": None, "head_sha": None, "git_error": None,
            "visible_pass": None, "original_pass": None, "verifier_error": None, "proxy_records": 0,
            "proxy_status_counts": {}, "proxy_incomplete": None, "home_instruction_files": [], "work_root": None}


def prepare(a) -> dict:
    task = Path(a.task).resolve(); t = read_task(task)
    if t["kind"] == "twin" and a.state != "A":
        raise SystemExit(f"refusing: twin task {t['task_id']} only runs in State A (PLAN line 62)")
    if a.state not in STATES:
        raise SystemExit(f"unknown state {a.state}")
    env_dir = task / ENV_DIRS[a.state]
    if not env_dir.is_dir():
        raise SystemExit(f"refusing: {env_dir} does not exist (build it with tasks/build_state_b.py or build_fixable.py)")
    native = a.body == "antigravity"
    run_id = getattr(a, "run_id", None) or make_run_id(t, a)
    wroot = (Path(os.environ.get("HS_WORK_ROOT", "/tmp/hs-work")) / run_id).resolve()
    check_ancestors(wroot.parent)
    home_files = home_instruction_files() if native else []
    if native and home_files and os.environ.get("HS_ALLOW_HOME_INSTRUCTIONS") != "1":
        raise SystemExit(f"refusing: antigravity runs under the real HOME and these instruction files exist: "
                         f"{', '.join(home_files)} (move them, or set HS_ALLOW_HOME_INSTRUCTIONS=1 and record it)")
    work = wroot / "work"; home = wroot / "home"
    shutil.copytree(env_dir, work, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache")); home.mkdir(parents=True)
    ifile = instruction_file(a.state, a.level, a.instruction)
    text = ifile.read_text().replace("{entry_point}", t["entry_point"]).rstrip("\n") + "\n"
    (work / "README.md").write_text("# Task\n\n" + text)
    (wroot / "prompt.md").write_text(text)
    git(work, "init", "-q", "."); git(work, "add", "-A"); git(work, "commit", "-q", "-m", "seed")
    seed_sha = git(work, "rev-parse", "HEAD", capture=True).stdout.strip()
    token = "hs_" + run_id
    proxy = None if native else a.proxy  # decided here, before compose(): the config files carry this exact URL
    comp = compose(a.body, a.model, home, work, proxy, token, text, max_turns=MAX_TURNS, agy_model=a.agy_model,
                   effort=a.agy_effort, write=True)
    if not native and not a.skip_health:
        try:
            import urllib.request
            with urllib.request.urlopen(f"{a.proxy}/health", timeout=5) as r:
                h = json.loads(r.read().decode())
            if not h.get("ok"):
                raise SystemExit(f"proxy {a.proxy}/health did not answer ok")
        except SystemExit:
            raise
        except Exception as e:
            raise SystemExit(f"proxy {a.proxy}/health unreachable: {e} (start study/runner/proxy.py first)")
    out_dir = Path(a.out).resolve() / run_id
    in_container = getattr(a, "in_container", None)
    versions = IMAGE_VERSIONS_FILE
    manifest = base_manifest(t, task, run_id, a, "docker" if in_container else a.sandbox, in_container or None)
    manifest.update({
        "model": comp["model"], "agy_model": a.agy_model if native else None, "agy_effort": a.agy_effort if native else None,
        "cmd": ["<task>" if c == text else c for c in comp["argv"]], "env_names": sorted(comp["env"]), "proxy": proxy,
        "instruction_file": str(ifile), "instruction_sha": sha(ifile.read_bytes()),
        "readme_sha": sha(text), "simple_prompt": os.environ.get("HS_SIMPLE_PROMPT", "1") if a.body == "claude" else None,
        "tool_search": os.environ.get("HS_TOOL_SEARCH", "false") if a.body == "claude" else None,
        "body_version": body_version(comp["argv"][0]),  # the binary that runs: inside the container when --in-container
        "image_versions": versions.read_text() if in_container and versions.exists() else None,
        "max_turns": MAX_TURNS if a.body == "claude" else None, "seed_sha": seed_sha,
        "home_instruction_files": home_files, "work_root": str(wroot)})
    prep = {"prep_json": str(wroot / "prep.json"), "run_id": run_id, "work": str(work), "home": str(home),
            "wroot": str(wroot), "prompt_file": str(wroot / "prompt.md"), "argv": comp["argv"], "env": comp["env"],
            "native": native, "out_dir": str(out_dir), "manifest": manifest, "task_path": str(task), "state": a.state,
            "proxy_log": str(Path(a.proxy_log).resolve()), "keep_work": a.keep_work, "python": a.python}
    (wroot / "prep.json").write_text(json.dumps(prep, indent=2))
    return prep


def launch(prep: dict) -> dict:
    """Run the body on this machine under the wall clock. (--sandbox docker wraps this whole script, see run_in_docker.)"""
    out = Path(prep["out_dir"]); out.mkdir(parents=True, exist_ok=True)
    m = prep["manifest"]; m["started"] = time.time()
    argv, env = prep["argv"], dict(prep["env"])
    with open(out / "stdout.log", "wb") as so, open(out / "stderr.log", "wb") as se:
        try:
            r = subprocess.run(argv, cwd=prep["work"], env=env, stdin=subprocess.DEVNULL, stdout=so, stderr=se,
                               timeout=WALL_CLOCK_S)
            m["exit"] = r.returncode; m["timed_out"] = False
        except subprocess.TimeoutExpired:
            m["exit"] = None; m["timed_out"] = True
        except OSError as e:  # FileNotFoundError, PermissionError, exec errors
            m["exit"] = 127; m["timed_out"] = False; m["launch_error"] = str(e); se.write(f"launch failed: {e}\n".encode())
    m["ended"] = time.time()
    return prep


def _record_key(name: str) -> str:
    """`<run_id>__<n>__req.json` and `<run_id>__<n>__resp.json` are one request; any other name is its own record."""
    for suf in ("__req.json", "__resp.json"):
        if name.endswith(suf):
            return name[:-len(suf)]
    return name[:-len(".json")] if name.endswith(".json") else name


def collect_proxy(log: Path, run_id: str, dest: Path, wait_s: float = PROXY_WAIT_S) -> dict:
    """Move the run's proxy records from the log dir into dest, waiting up to wait_s for records still being written
    (a `*.part` file, or a request whose response file has not landed yet). Returns
    {records, status_counts, incomplete}: records = number of requests (a req/resp pair or a single-file record),
    status_counts = HTTP status distribution of the responses ("missing" for a request without a response,
    "unknown" for a record without a status)."""
    dest.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + wait_s
    while True:
        parts = list(log.glob(f"{run_id}__*.part")) if log.exists() else []
        names = {f.name for f in log.glob(f"{run_id}__*.json")} if log.exists() else set()
        names |= {f.name for f in dest.glob(f"{run_id}__*.json")}
        reqs = {_record_key(n) for n in names if n.endswith("__req.json")}
        resps = {_record_key(n) for n in names if n.endswith("__resp.json")}
        pending = bool(parts) or bool(reqs - resps)
        if not pending or time.time() >= deadline:
            break
        time.sleep(0.5)
    if log.exists():
        for f in sorted(log.glob(f"{run_id}__*.json")):
            shutil.move(str(f), dest / f.name)
    keys: dict[str, str | None] = {}
    for f in sorted(dest.glob("*.json")):
        k = _record_key(f.name)
        if f.name.endswith("__req.json"):
            keys.setdefault(k, None); continue
        try:
            st = json.loads(f.read_text()).get("status")
        except Exception:
            st = None
        keys[k] = "unknown" if st is None else str(st)
    counts: dict[str, int] = {}
    for st in keys.values():
        st = st or "missing"
        counts[st] = counts.get(st, 0) + 1
    return {"records": len(keys), "status_counts": dict(sorted(counts.items())), "incomplete": pending}


def record_events(out: "Path | None") -> int:
    """Number of JSON-object lines in <out>/stdout.log, the stream-json record of a native (Antigravity) run."""
    if out is None or not (out / "stdout.log").exists():
        return 0
    n = 0
    for line in (out / "stdout.log").read_text(errors="replace").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                if isinstance(json.loads(line), dict):
                    n += 1
            except Exception:
                pass
    return n


def run_status(m: dict, native: bool, out: "Path | None" = None) -> tuple[str, str]:
    """(status, reason) per the manifest contract; the proxy counts must already be in m. A native body has no proxy
    record, so its own stream-json (stdout.log under `out`) stands in: no events means the body never ran, and the run
    is launch_failed rather than a silent give_up."""
    if m.get("timed_out"):
        return "timed_out", f"wall clock {m.get('wall_clock_s')} s hit"
    if m.get("launch_error") or m.get("exit") == 127:
        return "launch_failed", m.get("launch_error") or "exit 127 (binary not found)"
    if native:
        n = record_events(out)
        m["record_events"] = n
        if n == 0:
            return "launch_failed", "native body: no stream-json record (stdout.log missing or empty)"
        return "completed", f"native body: {n} stream-json events, no proxy"
    counts = m.get("proxy_status_counts") or {}
    if not m.get("proxy_records"):
        return "launch_failed", "no request reached the proxy"
    if any(k.isdigit() and 200 <= int(k) < 300 for k in counts):
        return "completed", f"{sum(v for k, v in counts.items() if k.isdigit() and 200 <= int(k) < 300)} 2xx responses"
    return "upstream_error", "no 2xx response: " + ", ".join(f"{k} x{v}" for k, v in counts.items())


def finish(prep: dict) -> dict:
    out = Path(prep["out_dir"]); out.mkdir(parents=True, exist_ok=True)
    work = Path(prep["work"]); wroot = Path(prep["wroot"]); m = prep["manifest"]
    if m.get("started") is None:
        m["started"] = m["ended"] = time.time()
    if m.get("ended") is None:
        m["ended"] = time.time()
    # diff against the seed commit, never HEAD: a body that commits its edits would otherwise show an empty diff
    seed = m.get("seed_sha")
    if not seed:  # a prep.json from before the seed sha was recorded: the root commit is the seed
        r0 = git(work, "rev-list", "--max-parents=0", "HEAD", capture=True, check=False)
        seed = r0.stdout.split()[0] if r0.returncode == 0 and r0.stdout.split() else "HEAD"
    m["seed_sha"] = seed
    untracked = git(work, "ls-files", "--others", "--exclude-standard", capture=True, check=False).stdout.split()
    if untracked:  # files the body created are part of the action too
        git(work, "add", "-N", *untracked, check=False)
    d = git(work, "diff", seed, capture=True, check=False)
    (out / "diff.patch").write_text(d.stdout)
    m["diff_stat"] = git(work, "diff", "--stat", seed, capture=True, check=False).stdout
    if d.returncode != 0:
        m["git_error"] = (d.stderr or f"git diff {seed} exit {d.returncode}").strip()[:500]
    head = git(work, "rev-parse", "HEAD", capture=True, check=False)
    m["head_sha"] = head.stdout.strip() if head.returncode == 0 else None
    n = git(work, "rev-list", "--count", f"{seed}..HEAD", capture=True, check=False)
    m["body_commits"] = int(n.stdout.strip()) if n.returncode == 0 and n.stdout.strip().isdigit() else None
    if (out / "work_final").exists():
        shutil.rmtree(out / "work_final")
    shutil.copytree(work, out / "work_final", ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    r = reruns(prep["task_path"], prep["state"], work, prep.get("python") or sys.executable)
    (out / "verifier.log").write_text(format_log(r))
    m["visible_pass"] = r["visible"]; m["original_pass"] = r["original"]; m["verifier_error"] = r["error"]
    fm = wroot / "final_message.txt"  # codex --output-last-message
    if fm.exists():
        shutil.copy(fm, out / "final_message.txt")
    if not prep["native"]:
        c = collect_proxy(Path(prep["proxy_log"]), prep["run_id"], out / "proxy")
        m["proxy_records"] = c["records"]; m["proxy_status_counts"] = c["status_counts"]; m["proxy_incomplete"] = c["incomplete"]
    m["status"], m["status_reason"] = run_status(m, prep["native"], out)
    (out / "manifest.json").write_text(json.dumps(m, indent=2))
    if not prep.get("keep_work"):
        shutil.rmtree(wroot, ignore_errors=True)
    return m


def shared_roots() -> list[Path]:
    """Trees the Docker VM can bind-mount from this host (colima shares $HOME; the repository normally lies in it)."""
    return [Path.home().resolve(), STUDY.parent.resolve()]


def check_shared(label: str, p: Path):
    if not any(p == r or r in p.parents for r in shared_roots()):
        raise SystemExit(f"refusing: {label} {p} lies outside $HOME and the repository, the only trees the Docker VM "
                         f"shares with this host (colima); put it under $HOME or run with --sandbox host")


def docker_argv(a, run_id: str) -> list[str]:
    """`docker run` that executes this script inside the image with every path at its host location."""
    study = STUDY.resolve(); repo = study.parent
    out = Path(a.out).resolve(); task = Path(a.task).resolve(); plog = Path(a.proxy_log).resolve()
    instr = Path(a.instruction).resolve() if a.instruction else None
    check_shared("the study dir", study); check_shared("--out", out); check_shared("--task", task); check_shared("--proxy-log", plog)
    if instr:
        check_shared("--instruction", instr)
    mounts: list[tuple[Path, str]] = [(study, "ro")]
    for p in (task, instr):
        if p and not (p == study or study in p.parents):
            mounts.append((p, "ro"))
    mounts += [(out, "rw"), (plog, "rw")]  # nested under the read-only study mount when they lie inside it
    cmd = ["docker", "run", "--rm", "--name", f"mrh-{run_id}", f"--add-host={DOCKER_HOST}:host-gateway",
           "--dns", DOCKER_DNS_SINK,  # no resolver inside the sandbox: only /etc/hosts (the proxy) resolves (LOG Sept 4 03:40)
           "--user", f"{os.getuid()}:{os.getgid()}", "-e", f"HOME={CONTAINER_HOME}", "-e", f"HS_WORK_ROOT={CONTAINER_WORK_ROOT}",
           "--tmpfs", f"{CONTAINER_WORK_ROOT}:rw,size=2g", "-w", str(repo)]
    for k in ("HS_SIMPLE_PROMPT", "HS_TOOL_SEARCH", "HS_EFFORT"):
        if k in os.environ:
            cmd += ["-e", f"{k}={os.environ[k]}"]
    for p, mode in mounts:
        cmd += ["-v", f"{p}:{p}:{mode}"]
    cmd += [a.image, "python3", str(study / "runner" / "run.py"), "--task", str(task), "--body", a.body, "--state", a.state,
            "--level", str(a.level), "--sample", str(a.sample), "--out", str(out), "--model", a.model, "--sandbox", "host",
            "--in-container", a.image, "--run-id", run_id, "--proxy", container_proxy(a.proxy), "--proxy-log", str(plog),
            "--python", "python3"]
    if instr:
        cmd += ["--instruction", str(instr)]
    if a.skip_health:
        cmd += ["--skip-health"]
    return cmd


def probe_mount(image: str) -> tuple[str, str] | None:
    """The study dir must be visible inside the container (an unshared tree shows up empty). None when fine, else
    ("launch", why) when docker itself cannot run the image, ("mount", why) when the bind mount is empty."""
    study = STUDY.resolve()
    try:
        r = subprocess.run(["docker", "run", "--rm", "-v", f"{study}:{study}:ro", image, "test", "-f",
                            str(study / "runner" / "run.py")], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "launch", f"docker unavailable: {e}"
    if r.returncode == 0:
        return None
    if r.returncode in DOCKER_LAUNCH_EXITS:
        return "launch", f"docker run exit {r.returncode}: {(r.stderr or r.stdout).strip()[-300:]}"
    return "mount", (f"the study dir {study} is empty inside the container (the Docker VM does not share it; colima shares "
                     f"only $HOME unless colima.yaml `mounts:` names more); move the repository under $HOME or use --sandbox host")


def run_in_docker(a) -> dict:
    task = Path(a.task).resolve(); t = read_task(task); run_id = make_run_id(t, a)
    out = Path(a.out).resolve(); rd = out / run_id; plog = Path(a.proxy_log).resolve()
    cmd = docker_argv(a, run_id)
    m = base_manifest(t, task, run_id, a, "docker", a.image); m["proxy"] = container_proxy(a.proxy); m["model"] = a.model
    m["network"] = f"dns-blocked (--dns {DOCKER_DNS_SINK}; raw IPs not filtered)"
    problem = probe_mount(a.image)
    if problem and problem[0] == "mount":
        raise SystemExit("refusing: " + problem[1])
    out.mkdir(parents=True, exist_ok=True); plog.mkdir(parents=True, exist_ok=True)
    m["started"] = time.time(); stdout = stderr = ""; exit_code = None
    if problem:
        m["exit"] = 127; m["timed_out"] = False; m["launch_error"] = problem[1]
    else:
        try:
            r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=WALL_CLOCK_S + FINISH_GRACE_S)
            exit_code = r.returncode; stdout, stderr = r.stdout, r.stderr; m["exit"] = exit_code; m["timed_out"] = False
        except subprocess.TimeoutExpired as e:
            subprocess.run(["docker", "kill", f"mrh-{run_id}"], stdin=subprocess.DEVNULL, capture_output=True)
            m["exit"] = None; m["timed_out"] = True
            stdout = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr = (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        except OSError as e:
            m["exit"] = 127; m["timed_out"] = False; m["launch_error"] = f"docker: {e}"
    m["ended"] = time.time()
    mf = rd / "manifest.json"
    if mf.exists():  # the inner run.py archived the run; its manifest is the record
        inner = json.loads(mf.read_text())
        if stderr.strip():
            (rd / "docker.log").write_text(stderr)
        return inner
    if exit_code not in (None,) + DOCKER_LAUNCH_EXITS and m.get("launch_error") is None and not m["timed_out"]:
        # the inner script refused or crashed before archiving (a refusal message on stderr): mirror it, no archive
        sys.stderr.write(stderr); raise SystemExit(exit_code)
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "docker.log").write_text(f"$ {' '.join(cmd)}\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n"
                                   + (f"launch failed: {m['launch_error']}\n" if m.get("launch_error") else ""))
    if exit_code in DOCKER_LAUNCH_EXITS and m.get("launch_error") is None:
        m["launch_error"] = f"docker run exit {exit_code}: {stderr.strip()[-300:]}"; m["exit"] = 127
    c = collect_proxy(plog, run_id, rd / "proxy", wait_s=PROXY_WAIT_S if m["timed_out"] else 0)
    m["proxy_records"] = c["records"]; m["proxy_status_counts"] = c["status_counts"]; m["proxy_incomplete"] = c["incomplete"]
    m["status"], m["status_reason"] = run_status(m, False)
    mf.write_text(json.dumps(m, indent=2))
    return m


def summary(m: dict) -> str:
    return json.dumps({"run_id": m["run_id"], "status": m.get("status"), "exit": m["exit"], "timed_out": m["timed_out"],
                       "visible_pass": m["visible_pass"], "original_pass": m["original_pass"],
                       "verifier_error": m["verifier_error"], "diff": (m["diff_stat"] or "").strip().splitlines()[-1:]})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task"); ap.add_argument("--body", choices=BODIES)
    ap.add_argument("--state", default="A", choices=STATES); ap.add_argument("--level", type=int, default=1, choices=(1, 2, 3))
    ap.add_argument("--sample", type=int, default=0); ap.add_argument("--out", default=str(STUDY / "runs"))
    ap.add_argument("--model", default=MODEL_DEFAULT); ap.add_argument("--sandbox", choices=("docker", "host"), default=None)
    ap.add_argument("--proxy", default=default_proxy()); ap.add_argument("--proxy-log", default=str(STUDY / "runs" / "proxy-log"))
    ap.add_argument("--instruction", default=None, help="override the instruction file (recorded in the manifest)")
    ap.add_argument("--agy-model", default=AGY_MODEL_DEFAULT); ap.add_argument("--agy-effort", default=AGY_EFFORT_DEFAULT)
    ap.add_argument("--image", default="harness-study"); ap.add_argument("--python", default=sys.executable, help="python for the reruns")
    ap.add_argument("--prepare-only", action="store_true"); ap.add_argument("--finish", default=None, metavar="PREP.json")
    ap.add_argument("--keep-work", action="store_true"); ap.add_argument("--skip-health", action="store_true", help="tests only")
    ap.add_argument("--in-container", default=None, help=argparse.SUPPRESS)  # set by run_in_docker on the inner call
    ap.add_argument("--run-id", default=None, help=argparse.SUPPRESS)  # set by run_in_docker so host and container agree
    a = ap.parse_args(argv)
    if a.finish:
        prep = json.loads(Path(a.finish).read_text())
        if a.keep_work:
            prep["keep_work"] = True
        m = finish(prep)
        print(json.dumps({"run_id": m["run_id"], "status": m.get("status"), "out_dir": prep["out_dir"],
                          "visible_pass": m["visible_pass"], "original_pass": m["original_pass"], "verifier_error": m["verifier_error"]}))
        return 0
    if not a.task or not a.body:
        ap.error("--task and --body are required")
    if a.body == "antigravity":
        a.sandbox = "host"  # vendor-native: signed in on this host, never containerised
    elif a.sandbox is None:
        a.sandbox = "host" if a.prepare_only else "docker"  # a hand run is launched on this host by its pane
    if a.sandbox == "docker":
        if a.prepare_only:
            ap.error("--prepare-only prepares a run for a pane on this host: use --sandbox host")
        print(summary(run_in_docker(a)))
        return 0
    prep = prepare(a)
    if a.prepare_only:
        print(json.dumps({k: prep[k] for k in ("prep_json", "run_id", "work", "home", "wroot", "prompt_file", "argv",
                                                "env", "native", "out_dir")}))
        return 0
    launch(prep)
    print(summary(finish(prep)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
