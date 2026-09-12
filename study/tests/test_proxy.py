"""proxy.py: /health without forwarding; run-token attribution; the token never reaches a record; --no-upstream logs;
chunked request bodies; two records per request (req at request time, resp before the terminating chunk); a client
that disconnects mid-stream; two runs writing distinct files; an unreachable upstream; load_records joins the pairs."""
import json, socket, threading, time, urllib.error, urllib.request
from pathlib import Path

import pytest

import proxy
proxy.PROVIDER_PIN = ""  # tests forward bodies unchanged


SSE = [b'data: {"model":"google/gemini-3.8-flash","choices":[{"delta":{"content":"part%d"}}]}\n\n' % i for i in range(8)]


class FakeResp:
    status = 200

    def __init__(self, chunks, delay):
        self.chunks = list(chunks); self.delay = delay

    def getheaders(self):
        return [("Content-Type", "text/event-stream"), ("Content-Length", "999"), ("X-Upstream", "fake")]

    def read(self, n=-1):
        if not self.chunks:
            return b""
        time.sleep(self.delay); return self.chunks.pop(0)


class FakeConn:
    """Stands in for http.client.HTTPSConnection: records what would have gone upstream, streams SSE back."""
    sent: list[dict] = []

    def __init__(self, chunks=SSE, delay=0.02):
        self.chunks = chunks; self.delay = delay

    def request(self, method, path, body=None, headers=None):
        FakeConn.sent.append({"method": method, "path": path, "body": body, "headers": dict(headers or {})})

    def getresponse(self):
        return FakeResp(self.chunks, self.delay)


def _start(tmp_path, upstream=False):
    srv = proxy.serve(0, tmp_path / "log", upstream=upstream, real_key="sk-or-REALKEY-not-for-disk", background=True)
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _post(base, body: bytes, headers: dict, path="/api/v1/chat/completions"):
    req = urllib.request.Request(base + path, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        data = e.read(); e.close(); return e.code, data


def _names(log: Path) -> list[str]:
    return sorted(p.name for p in log.iterdir())


def test_health_does_not_forward(tmp_path):
    srv, base = _start(tmp_path)
    try:
        with urllib.request.urlopen(base + "/health", timeout=5) as r:
            h = json.loads(r.read())
        assert h == {"ok": True, "upstream": "openrouter.ai", "key": "set"}
        assert not list((tmp_path / "log").glob("*.json"))
    finally:
        srv.shutdown(); srv.server_close()


def test_record_attributes_run_and_drops_token(tmp_path):
    srv, base = _start(tmp_path)
    try:
        body = json.dumps({"model": "google/gemini-3.8-flash", "messages": [{"role": "user", "content": "hi"}]}).encode()
        code, _ = _post(base, body, {"Authorization": "Bearer hs_run-abc__claude__A1__s0", "Content-Type": "application/json"})
        assert code == 503
        assert _names(tmp_path / "log") == ["run-abc__claude__A1__s0__0001__req.json", "run-abc__claude__A1__s0__0001__resp.json"]
        req = json.loads((tmp_path / "log" / "run-abc__claude__A1__s0__0001__req.json").read_text())
        resp = json.loads((tmp_path / "log" / "run-abc__claude__A1__s0__0001__resp.json").read_text())
        assert req["run_id"] == "run-abc__claude__A1__s0" and req["n"] == 1 and req["request"]["model"] == "google/gemini-3.8-flash"
        assert resp["run_id"] == req["run_id"] and resp["status"] == 503 and resp["response_truncated"] is False
        for p in (tmp_path / "log").glob("*.json"):
            raw = p.read_text(); assert "hs_run-abc" not in raw and "REALKEY" not in raw
        recs = proxy.load_records(tmp_path / "log")
        assert len(recs) == 1 and recs[0]["request"]["model"] == "google/gemini-3.8-flash" and recs[0]["status"] == 503
        assert recs[0]["resp_missing"] is False and recs[0]["id"] == "run-abc__claude__A1__s0__0001"
    finally:
        srv.shutdown(); srv.server_close()


def test_x_api_key_token_and_anon(tmp_path):
    srv, base = _start(tmp_path)
    try:
        for hdrs, prefix in (({"x-api-key": "hs_xyz"}, "xyz__0001__"), ({}, "_anon__0001__")):
            _post(base, b"{}", hdrs, path="/api/v1/messages")
            assert any(p.name.startswith(prefix) for p in (tmp_path / "log").glob("*.json"))
    finally:
        srv.shutdown(); srv.server_close()


def test_refuses_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        proxy.main(["--port", "0", "--log", str(tmp_path / "l")])


def test_chunked_request_body_is_read_and_forwarded(tmp_path, monkeypatch):
    """a body sent with Transfer-Encoding: chunked (no Content-Length) reaches the record and the upstream."""
    monkeypatch.setattr(proxy, "connect", lambda: FakeConn()); FakeConn.sent.clear()
    srv, base = _start(tmp_path, upstream=True)
    try:
        body = b'{"model":"google/gemini-3.8-flash","messages":[{"role":"user","content":"chunked"}]}'
        s = socket.create_connection(("127.0.0.1", srv.server_address[1]), timeout=10)
        s.sendall(b"POST /api/v1/chat/completions HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer hs_chunk\r\n"
                  b"Content-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n")
        for piece in (body[:20], body[20:]):
            s.sendall(b"%x\r\n%s\r\n" % (len(piece), piece))
        s.sendall(b"0\r\n\r\n")
        data = b""
        while b"\r\n0\r\n\r\n" not in data:
            got = s.recv(65536)
            if not got:
                break
            data += got
        s.close()
        assert data.startswith(b"HTTP/1.1 200") and b"part7" in data
        req = json.loads((tmp_path / "log" / "chunk__0001__req.json").read_text())
        assert req["request"]["messages"][0]["content"] == "chunked" and req["request_raw_len"] == len(body)
        assert FakeConn.sent[-1]["body"] == body and "Transfer-Encoding" not in FakeConn.sent[-1]["headers"]
        assert FakeConn.sent[-1]["headers"]["Authorization"] == "Bearer sk-or-REALKEY-not-for-disk"
    finally:
        srv.shutdown(); srv.server_close()


def test_resp_record_on_disk_before_client_has_the_answer(tmp_path, monkeypatch):
    """by the time urlopen returns the whole streamed body, `__resp.json` exists and no `.part` remains."""
    monkeypatch.setattr(proxy, "connect", lambda: FakeConn())
    srv, base = _start(tmp_path, upstream=True)
    try:
        code, data = _post(base, b'{"model":"m","messages":[]}', {"Authorization": "Bearer hs_ok", "Content-Type": "application/json"})
        names = _names(tmp_path / "log")
        assert code == 200 and data == b"".join(SSE)
        assert names == ["ok__0001__req.json", "ok__0001__resp.json"]
        resp = json.loads((tmp_path / "log" / "ok__0001__resp.json").read_text())
        assert resp["response_text"] == b"".join(SSE).decode() and resp["model_ids_in_response"] == ["google/gemini-3.8-flash"]
        assert resp["client_disconnected"] is False and resp["ts_end"] >= resp["ts"]
    finally:
        srv.shutdown(); srv.server_close()


def test_client_disconnect_mid_stream_still_records_whole_response(tmp_path, monkeypatch):
    monkeypatch.setattr(proxy, "connect", lambda: FakeConn(delay=0.05))
    srv, base = _start(tmp_path, upstream=True)
    try:
        s = socket.create_connection(("127.0.0.1", srv.server_address[1]), timeout=10)
        body = b'{"model":"m","messages":[]}'
        s.sendall(b"POST /api/v1/chat/completions HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer hs_disc\r\n"
                  b"Content-Type: application/json\r\nContent-Length: %d\r\n\r\n%s" % (len(body), body))
        data = b""
        while b"part0" not in data:
            data += s.recv(65536)
        s.close()  # gone after the first chunk
        assert "disc__0001__req.json" in _names(tmp_path / "log")
        deadline = time.time() + 5
        while "disc__0001__resp.json" not in _names(tmp_path / "log") and time.time() < deadline:
            time.sleep(0.05)
        resp = json.loads((tmp_path / "log" / "disc__0001__resp.json").read_text())
        assert resp["client_disconnected"] is True and resp["status"] == 200
        assert all(f"part{i}" in resp["response_text"] for i in range(8))
        assert not [n for n in _names(tmp_path / "log") if n.endswith(".part")]
        with urllib.request.urlopen(base + "/health", timeout=5) as r:  # the server is still healthy
            assert json.loads(r.read())["ok"] is True
    finally:
        srv.shutdown(); srv.server_close()


def test_two_concurrent_runs_write_distinct_numbered_files(tmp_path, monkeypatch):
    monkeypatch.setattr(proxy, "connect", lambda: FakeConn(delay=0.01))
    srv, base = _start(tmp_path, upstream=True)
    try:
        results = {}

        def go(token, k):
            results[(token, k)] = _post(base, b'{"model":"m","messages":[]}', {"Authorization": f"Bearer hs_{token}"})

        ts = [threading.Thread(target=go, args=(t, k)) for t in ("r1", "r2") for k in (0, 1)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(10)
        assert all(v[0] == 200 for v in results.values())
        assert _names(tmp_path / "log") == ["r1__0001__req.json", "r1__0001__resp.json", "r1__0002__req.json", "r1__0002__resp.json",
                                            "r2__0001__req.json", "r2__0001__resp.json", "r2__0002__req.json", "r2__0002__resp.json"]
        recs = proxy.load_records(tmp_path / "log")
        assert sorted(r["id"] for r in recs) == ["r1__0001", "r1__0002", "r2__0001", "r2__0002"]
        assert {r["run_id"] for r in recs} == {"r1", "r2"} and all(not r["resp_missing"] for r in recs)
    finally:
        srv.shutdown(); srv.server_close()
    # a proxy restarted on the same log dir continues a run's numbering instead of reusing 0001
    srv2, base2 = _start(tmp_path, upstream=True)
    try:
        _post(base2, b"{}", {"Authorization": "Bearer hs_r1"})
        assert "r1__0003__req.json" in _names(tmp_path / "log") and "r1__0003__resp.json" in _names(tmp_path / "log")
    finally:
        srv2.shutdown(); srv2.server_close()


def test_unreachable_upstream_gets_502_and_a_resp_record(tmp_path, monkeypatch):
    def boom():
        raise OSError("dns down")
    monkeypatch.setattr(proxy, "connect", boom)
    srv, base = _start(tmp_path, upstream=True)
    try:
        code, data = _post(base, b"{}", {"Authorization": "Bearer hs_u"})
        assert code == 502 and b"upstream unreachable" in data
        resp = json.loads((tmp_path / "log" / "u__0001__resp.json").read_text())
        assert resp["status"] == 502 and resp["upstream_error"] == "dns down"
    finally:
        srv.shutdown(); srv.server_close()


def test_load_records_joins_pairs_and_passes_legacy_through(tmp_path):
    d = tmp_path / "px"; d.mkdir()
    (d / "run__0001__req.json").write_text(json.dumps({"id": "run__0001", "run_id": "run", "n": 1, "path": "/api/v1/messages",
                                                        "request": {"tools": [1]}, "request_raw_len": 12, "ts": 5.0}))
    (d / "run__0001__resp.json").write_text(json.dumps({"id": "run__0001", "run_id": "run", "n": 1, "path": "/api/v1/messages",
                                                         "status": 200, "response_text": "ok", "response_truncated": False,
                                                         "model_ids_in_response": ["m"], "ts": 5.0, "ts_end": 6.0}))
    (d / "run__0002__req.json").write_text(json.dumps({"id": "run__0002", "run_id": "run", "n": 2, "path": "/api/v1/messages",
                                                        "request": {"tools": [1]}, "request_raw_len": 12, "ts": 7.0}))
    (d / "legacy__20260902T100000_00000000.json").write_text(json.dumps({"id": "legacy", "ts": 1.0, "path": "/x", "request": None,
                                                                           "response_text": "", "status": 503}))
    recs = proxy.load_records(d)
    assert [r["id"] for r in recs] == ["legacy", "run__0001", "run__0002"]
    assert recs[1]["request"] == {"tools": [1]} and recs[1]["response_text"] == "ok" and recs[1]["status"] == 200 and not recs[1]["resp_missing"]
    assert recs[2]["resp_missing"] is True and recs[2]["status"] is None and recs[2]["request"] == {"tools": [1]}


def test_load_records_marks_a_corrupt_half(tmp_path):
    d = tmp_path / "px"; d.mkdir()
    (d / "run__0001__req.json").write_text(json.dumps({"id": "run__0001", "run_id": "run", "n": 1, "path": "/api/v1/messages",
                                                        "request": {"tools": [1]}, "request_raw_len": 12, "ts": 5.0}))
    (d / "run__0001__resp.json").write_text('{"id": "run__0001", "status": 200, "resp')
    (d / "run__0002__req.json").write_text("{not json")
    (d / "run__0002__resp.json").write_text(json.dumps({"id": "run__0002", "run_id": "run", "n": 2, "path": "/api/v1/messages",
                                                         "status": 200, "response_text": "ok", "response_truncated": False,
                                                         "model_ids_in_response": [], "ts": 6.0, "ts_end": 7.0}))
    recs = {r["id"]: r for r in proxy.load_records(d)}
    assert recs["run__0001"]["_bad"].startswith("run__0001__resp.json: ") and recs["run__0001"]["request"] == {"tools": [1]}
    assert recs["run__0001"]["status"] is None and recs["run__0001"]["resp_missing"] is False
    assert recs["run__0002"]["_bad"].startswith("run__0002__req.json: ") and recs["run__0002"]["status"] == 200
