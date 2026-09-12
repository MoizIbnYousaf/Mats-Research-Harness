#!/usr/bin/env python3
"""Live wall of every running mrh container: body, task, state, elapsed, turns, and the last assistant line, from
the proxy's request records (each request carries the whole conversation). Demo view only; nothing here is a number.

wall.py [--seconds 90] [--every 2] [--proxy-log study/runs/proxy-log]
"""
import argparse, glob, json, os, re, subprocess, sys, time
from pathlib import Path


def live_runs():
    out = subprocess.run(["docker", "ps", "--format", "{{.Names}}\t{{.RunningFor}}"], capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        name, _, age = line.partition("\t")
        if name.startswith("mrh-"):
            rows.append((name[4:], age.replace(" ago", "")))
    return rows


def last_assistant(req_path: Path) -> str:
    try:
        raw = req_path.read_text(errors="replace")
    except Exception:
        return ""
    # last assistant turn in any wire format: find the last '"role": "assistant"' and pull text after it
    i = raw.rfind('"role": "assistant"')
    if i < 0:
        i = raw.rfind('"role":"assistant"')
    if i < 0:
        return ""
    seg = raw[i:i + 4000]
    m = re.search(r'"(?:text|content|arguments|command|cmd)":\s*"((?:[^"\\]|\\.){8,400})', seg)
    if not m:
        return ""
    s = m.group(1).encode().decode("unicode_escape", errors="ignore")
    return " ".join(s.split())


def snapshot(plog: Path):
    reqs = {}
    for f in glob.glob(str(plog / "*req.json")):
        rid = os.path.basename(f).split("__0")[0] if "__0" in os.path.basename(f) else None
        # file names: <run_id>__NNNN__req.json ; run ids contain double underscores too, so split on the counter
        m = re.match(r"(.*)__(\d{4})__req\.json$", os.path.basename(f))
        if not m:
            continue
        rid, n = m.group(1), int(m.group(2))
        if rid not in reqs or n > reqs[rid][0]:
            reqs[rid] = (n, Path(f))
    rows = []
    for rid, age in live_runs():
        parts = rid.split("__")
        task = parts[0].split(".", 1)[-1] if parts else rid
        body = parts[1] if len(parts) > 1 else "?"
        cell = parts[2] if len(parts) > 2 else "?"
        n, f = reqs.get(rid, (0, None))
        last = last_assistant(f) if f else ""
        rows.append((body, task, cell, age, n, last))
    rows.sort()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=90); ap.add_argument("--every", type=float, default=2.0)
    ap.add_argument("--proxy-log", default="study/runs/proxy-log"); ap.add_argument("--width", type=int, default=150)
    a = ap.parse_args()
    plog = Path(a.proxy_log)
    t0 = time.time()
    while time.time() - t0 < a.seconds:
        rows = snapshot(plog)
        sys.stdout.write("\033[2J\033[H")
        print(f"\033[1m mrh wall  {time.strftime('%H:%M:%S')}   {len(rows)} containers running   one model, four harnesses, DNS-blocked sandbox\033[0m")
        print(f" {'body':9s} {'task':22s} {'cell':9s} {'age':>7s} {'turns':>5s}  last assistant line")
        print(" " + "-" * (a.width - 2))
        for body, task, cell, age, n, last in rows:
            w = a.width - 62
            print(f" {body:9s} {task[:22]:22s} {cell:9s} {age:>7s} {n:5d}  {last[:w]}")
        sys.stdout.flush()
        time.sleep(a.every)


if __name__ == "__main__":
    main()
