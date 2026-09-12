#!/usr/bin/env python3
"""Localhost logging proxy in front of OpenRouter (PLAN v3 lines 30, 33).

Every request and response body is written to the log dir, so each body's exact system prompt, tool list, message
history, model id per response and usage are on disk per request. SSE streams pass through unchanged.

Per-run attribution: the CLIs never hold the real key. They hold a run token `hs_<run_id>` in OPENROUTER_API_KEY /
ANTHROPIC_AUTH_TOKEN. The proxy reads `Authorization: Bearer hs_...` or `x-api-key: hs_...`, sets run_id = token[3:],
and replaces both headers with the real OPENROUTER_API_KEY from its own environment. The real key exists in this
process only.

Records, two files per request, numbered per run in arrival order:
  `<run_id or _anon>__<n>__req.json`   written when the request has been read, before anything is forwarded;
  `<run_id or _anon>__<n>__resp.json`  written when the upstream response is complete (streamed responses included),
                                       and before the terminating chunk reaches the client, so a client that has the
                                       whole answer can rely on the record being on disk.
A record is written to `.part` and renamed, so a half-written file never carries the final name. A client that
disconnects mid-stream does not stop the upstream read: the resp record still holds the whole response and
`client_disconnected: true`. An upstream that cannot be reached gets a resp record with status 502 and `upstream_error`.
run.py moves `<run_id>__*.json` into the run dir; `load_records(dir)` joins the pairs back into one dict per request
(and passes older single-file records through) for the parser.

Request bodies arrive with Content-Length or with `Transfer-Encoding: chunked`; both are read in full.

GET /health answers 200 {"ok": true, "upstream": "openrouter.ai", "key": "set|unset"} without forwarding.
--no-upstream never opens a socket to openrouter.ai: it answers 503 but still logs (tests, doctor).

Run: python study/runner/proxy.py [--port 8931] [--log study/runs/proxy-log] [--bind 127.0.0.1] [--no-upstream]
"""
import argparse, http.client, json, os, re, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

UPSTREAM = "openrouter.ai"
PROVIDER_PIN = os.environ.get("HS_PROVIDER_PIN", '{"order": ["deepinfra", "parasail", "baseten", "coreweave", "akashml", "openinference", "novita"], "allow_fallbacks": false}')  # empty disables; a bare name pins that provider
def provider_field():
    """The OpenRouter `provider` object injected into every model call (LOG Sept 4 04:45): a JSON object as given, or
    a bare provider name as {"order": [name], "allow_fallbacks": false}."""
    if not PROVIDER_PIN:
        return None
    return json.loads(PROVIDER_PIN) if PROVIDER_PIN.strip().startswith("{") else {"order": [PROVIDER_PIN], "allow_fallbacks": False}
EMPTY_RETRIES = int(os.environ.get("HS_EMPTY_RETRIES", "3"))  # Anthropic route only; see _fwd
PIN_PATHS = ("/api/v1/chat/completions", "/api/v1/messages", "/api/v1/responses")
HOP = {"host", "connection", "keep-alive", "transfer-encoding", "content-length", "accept-encoding"}
RESPONSE_CAP = 4_000_000
STUDY = Path(__file__).resolve().parent.parent
DEFAULT_LOG = STUDY / "runs" / "proxy-log"
TOKEN_RE = re.compile(r"^(?:Bearer\s+)?(hs_[A-Za-z0-9_.\-]+)$")
REC_RE = re.compile(r"^(?P<base>.+)__(?P<n>\d+)__(?P<kind>req|resp)\.json$")


def connect():
    """The upstream connection; tests replace this with a fake that streams a canned response."""
    return http.client.HTTPSConnection(UPSTREAM, timeout=600)


def _models(resp: bytes):
    for m in re.finditer(rb'"model"\s*:\s*"([^"]+)"', resp):
        yield m.group(1).decode()


def _write_record(path: Path, rec: dict) -> None:
    tmp = path.with_name(path.name + ".part")
    with open(tmp, "w") as f:
        json.dump(rec, f)
    tmp.rename(path)


def load_records(d: Path) -> list[dict]:
    """One dict per request from a dir of proxy records: `__req` and `__resp` pairs joined on their number (a pair
    with no resp file gets status None and `resp_missing: true`; a half that is not valid JSON marks the joined record
    with `_bad: "<file>: <error>"`); any other `*.json` is an older single-file record and is passed through unchanged
    (a corrupt one carries `_bad` too). Sorted by (ts, id)."""
    pairs: dict[str, dict] = {}; out: list[dict] = []
    for f in sorted(Path(d).glob("*.json")):
        m = REC_RE.match(f.name)
        try:
            rec = json.loads(f.read_text())
        except Exception as e:
            rec = {"id": f.name, "ts": 0, "path": "", "request": None, "response_text": "", "_bad": str(e)}
        if not m:
            out.append(rec); continue
        key = f"{m['base']}__{m['n']}"
        slot = pairs.setdefault(key, {"id": key, "run_id": None, "n": int(m["n"]), "path": "", "status": None,
                                      "request": None, "request_raw_len": 0, "response_text": "",
                                      "response_truncated": False, "model_ids_in_response": [], "ts": 0,
                                      "resp_missing": True})
        if "_bad" in rec:
            slot["_bad"] = f"{f.name}: {rec['_bad']}"
        if m["kind"] == "req":
            slot.update({k: rec.get(k) for k in ("run_id", "path", "request", "request_raw_len", "ts")})
        else:
            slot.update({k: rec[k] for k in ("status", "response_text", "response_truncated", "model_ids_in_response") if k in rec})
            for k in ("client_disconnected", "upstream_error", "ts_end"):
                if k in rec:
                    slot[k] = rec[k]
            if not slot["path"]:
                slot["path"] = rec.get("path", ""); slot["run_id"] = rec.get("run_id")
            slot["resp_missing"] = False
    out += pairs.values()
    return sorted(out, key=lambda r: (r.get("ts") or 0, r.get("id", "")))


def make_handler(log_dir: Path, real_key: str | None, upstream: bool):
    log_dir.mkdir(parents=True, exist_ok=True)
    counters: dict[str, int] = {}; lock = threading.Lock()

    def next_n(base: str) -> int:
        with lock:
            if base not in counters:
                seen = [int(m["n"]) for p in log_dir.glob(f"{base}__*__req.json*")
                        if (m := REC_RE.match(p.name.removesuffix(".part"))) and m["base"] == base]
                counters[base] = max(seen, default=0)
            counters[base] += 1
            return counters[base]

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _health(self):
            body = json.dumps({"ok": True, "upstream": UPSTREAM, "key": "set" if real_key else "unset"}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def _run_id(self, hdrs: dict) -> str | None:
            for k in ("authorization", "x-api-key"):
                v = hdrs.get(k)
                if not v:
                    continue
                m = TOKEN_RE.match(v.strip())
                if m:
                    return m.group(1)[3:]
            return None

        def _read_body(self) -> bytes:
            te = (self.headers.get("transfer-encoding") or "").lower()
            if "chunked" in te:
                parts: list[bytes] = []
                while True:
                    line = self.rfile.readline(65537).strip()
                    if not line:
                        break
                    size = int(line.split(b";")[0], 16)
                    if size == 0:
                        while self.rfile.readline(65537) not in (b"\r\n", b"\n", b""):  # trailers
                            pass
                        break
                    parts.append(self.rfile.read(size)); self.rfile.readline(65537)  # the CRLF after the chunk
                return b"".join(parts)
            n = int(self.headers.get("content-length") or 0)
            return self.rfile.read(n) if n else b""

        def _client_write(self, data: bytes) -> bool:
            if self._client_gone:
                return False
            try:
                self.wfile.write(data); self.wfile.flush(); return True
            except (BrokenPipeError, ConnectionResetError, OSError):
                self._client_gone = True; self.close_connection = True; return False

        def _fwd(self):
            if self.command == "GET" and self.path.rstrip("/") == "/health":
                return self._health()
            self._client_gone = False
            body = self._read_body()
            hdrs = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
            lower = {k.lower(): v for k, v in hdrs.items()}
            run_id = self._run_id(lower)
            # strip whatever the CLI sent and put the real key in (never the run token)
            for k in list(hdrs):
                if k.lower() in ("authorization", "x-api-key", "x-title", "http-referer"):
                    del hdrs[k]
            if real_key:
                hdrs["Authorization"] = f"Bearer {real_key}"
            hdrs["Host"] = UPSTREAM; hdrs["Accept-Encoding"] = "identity"
            base = run_id or "_anon"; n = next_n(base); rid = f"{base}__{n:04d}"; ts = time.time()
            try:
                req_json = json.loads(body) if body else None
            except Exception:
                req_json = None
            pinned = None
            if PROVIDER_PIN and isinstance(req_json, dict) and self.path.split("?")[0] in PIN_PATHS:
                # one upstream provider for every body (LOG Sept 4 04:30): the same slug was served by 17 providers at
                # three quantizations, and the Anthropic route returned empty completions; OpenRouter honours this
                # field on /chat/completions, /messages and /responses (a non-serving provider errors "No endpoints found")
                req_json["provider"] = provider_field()
                body = json.dumps(req_json).encode()
                hdrs["Content-Length"] = str(len(body)); pinned = req_json["provider"]
            _write_record(log_dir / f"{rid}__req.json",
                          {"id": rid, "run_id": run_id, "n": n, "kind": "req", "method": self.command, "path": self.path,
                           "request": req_json, "request_raw_len": len(body), "ts": ts, "provider_pin": pinned})
            chunks: list[bytes] = []
            if not upstream:
                msg = json.dumps({"error": "proxy started with --no-upstream"}).encode()
                self._resp_record(rid, run_id, n, ts, 503, msg)  # on disk before the client sees the answer
                self.send_response(503); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(msg))); self.end_headers(); self._client_write(msg)
                return
            # Empty-completion retry (LOG Sept 4 05:00): on the Anthropic route the model sometimes answers a request
            # whose last message is a system-role reminder with an immediate end_turn (output_tokens 1, no content
            # block); Claude Code retries once and then ends its turn with no text. The proxy peeks at the stream until
            # the first content_block_start (real answer) or message_stop (empty) and re-requests up to EMPTY_RETRIES
            # times; every empty attempt is kept on the response record. Other routes stream through untouched.
            peek_empty = self.path.split("?")[0] == "/api/v1/messages"
            empty_attempts: list[dict] = []
            while True:
                try:
                    c = connect()
                    c.request(self.command, self.path, body=body, headers=hdrs)
                    r = c.getresponse()
                except Exception as e:
                    msg = json.dumps({"error": f"upstream unreachable: {e}"}).encode()
                    self._resp_record(rid, run_id, n, ts, 502, msg, upstream_error=str(e), empty_attempts=empty_attempts)
                    self.send_response(502); self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(msg))); self.end_headers(); self._client_write(msg)
                    return
                head = b""
                if peek_empty and r.status == 200:
                    empty = None
                    while empty is None:
                        chunk = r.read(4096)
                        if not chunk:
                            empty = b"content_block_start" not in head
                            break
                        head += chunk
                        if b"content_block_start" in head:
                            empty = False
                        elif b"message_stop" in head:
                            empty = True
                    if empty and len(empty_attempts) < EMPTY_RETRIES:
                        rest = r.read()
                        empty_attempts.append({"ts": time.time(), "text": (head + rest).decode("utf-8", "replace")[:4000]})
                        continue
                break
            self.send_response(r.status)
            for k, v in r.getheaders():
                if k.lower() not in HOP:
                    self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            try:
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError, OSError):
                self._client_gone = True; self.close_connection = True
            if head:
                chunks.append(head); self._client_write(b"%x\r\n%s\r\n" % (len(head), head))
            while True:
                chunk = r.read(4096)
                if not chunk:
                    break
                chunks.append(chunk); self._client_write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
            # the resp record is on disk before the terminating chunk, so a client holding the whole answer can rely on it
            self._resp_record(rid, run_id, n, ts, r.status, b"".join(chunks), client_disconnected=self._client_gone,
                              empty_attempts=empty_attempts)
            self._client_write(b"0\r\n\r\n")

        def _resp_record(self, rid: str, run_id: str | None, n: int, ts: float, status: int, resp: bytes, **extra):
            text = resp.decode("utf-8", "replace")
            rec = {"id": rid, "run_id": run_id, "n": n, "kind": "resp", "path": self.path, "status": status,
                   "response_text": text[:RESPONSE_CAP], "response_truncated": len(text) > RESPONSE_CAP,
                   "model_ids_in_response": sorted(set(_models(resp))), "ts": ts, "ts_end": time.time(), **extra}
            _write_record(log_dir / f"{rid}__resp.json", rec)

        do_POST = _fwd; do_GET = _fwd

    return H


def serve(port: int, log_dir: Path, bind: str = "127.0.0.1", upstream: bool = True, real_key: str | None = None,
          background: bool = False) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((bind, port), make_handler(log_dir, real_key, upstream))
    if background:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv
    srv.serve_forever()
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=int(os.environ.get("HS_PROXY_PORT") or 8931))
    ap.add_argument("--log", default=str(DEFAULT_LOG)); ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--no-upstream", action="store_true", help="never contact openrouter.ai; answer 503 but log")
    a = ap.parse_args(argv)
    key = os.environ.get("OPENROUTER_API_KEY") or None
    if not key and not a.no_upstream:
        sys.exit("proxy: OPENROUTER_API_KEY is not set in this environment; refuse to start (use --no-upstream for tests)")
    log_dir = Path(a.log).resolve()
    print(f"proxy on http://{a.bind}:{a.port} -> {'https://' + UPSTREAM if not a.no_upstream else 'no upstream'}, "
          f"logging to {log_dir}, key {'set' if key else 'unset'}", flush=True)
    serve(a.port, log_dir, a.bind, upstream=not a.no_upstream, real_key=key)


if __name__ == "__main__":
    main()
