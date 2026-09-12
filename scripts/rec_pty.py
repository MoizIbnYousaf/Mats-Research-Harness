#!/usr/bin/env python3
"""Record a full-screen terminal program into an asciinema v2 cast with an explicit PTY size (demo tooling only).

rec_pty.py --out FILE.cast --cols 220 --rows 60 --seconds 150 [--env K=V ...] -- CMD ARGS...

Spawns CMD in a fresh pty whose window size is set with TIOCSWINSZ before exec, so programs that read the size with
ioctl get the requested size (asciinema's own --cols/--rows only label the file). Output is timestamped into the cast;
after --seconds the child gets SIGINT, then SIGTERM. Render with `agg FILE.cast out.gif`.
"""
import argparse, fcntl, json, os, select, signal, struct, sys, termios, time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--cols", type=int, default=220); ap.add_argument("--rows", type=int, default=60)
    ap.add_argument("--seconds", type=float, default=150); ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--key", action="append", default=[], help="DELAY:TEXT, write TEXT to the pty DELAY seconds in (\\r for Enter)")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        sys.exit("no command")
    env = {"HOME": os.environ.get("HOME", ""), "PATH": os.environ.get("PATH", ""), "TERM": "xterm-256color",
           "LANG": "en_US.UTF-8", "COLUMNS": str(a.cols), "LINES": str(a.rows)}
    for kv in a.env:
        k, _, v = kv.partition("="); env[k] = v
    pid, fd = os.forkpty()
    if pid == 0:
        fcntl.ioctl(sys.stdin.fileno(), termios.TIOCSWINSZ, struct.pack("HHHH", a.rows, a.cols, 0, 0))
        os.execvpe(cmd[0], cmd, env)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", a.rows, a.cols, 0, 0))
    keys = sorted((float(k.partition(":")[0]), k.partition(":")[2].encode().decode("unicode_escape")) for k in a.key)
    t0 = time.time()
    with open(a.out, "w") as f:
        f.write(json.dumps({"version": 2, "width": a.cols, "height": a.rows, "timestamp": int(t0),
                            "env": {"TERM": "xterm-256color", "SHELL": "/bin/sh"}}) + "\n")
        n = 0
        while time.time() - t0 < a.seconds:
            while keys and time.time() - t0 >= keys[0][0]:
                os.write(fd, keys.pop(0)[1].encode())
            r, _, _ = select.select([fd], [], [], 0.25)
            if not r:
                continue
            try:
                data = os.read(fd, 65536)
            except OSError:
                break
            if not data:
                break
            f.write(json.dumps([round(time.time() - t0, 4), "o", data.decode("utf-8", "replace")]) + "\n"); n += 1
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                os.kill(pid, sig); time.sleep(0.5)
            except ProcessLookupError:
                break
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
    print(f"wrote {a.out}: {n} output events over {round(time.time() - t0)} s at {a.cols}x{a.rows}")


if __name__ == "__main__":
    main()
