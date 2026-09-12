#!/usr/bin/env python3
"""Proxy-log parser: the per-run records written by proxy.py -> Perception (PLAN v3 lines 30, 33).

Every request body carries the full message history, so the LAST agent record's request holds every tool result the
model saw; its SSE response holds the final assistant text. Agent records are those whose request declares tools
(chat/messages: request.tools non-empty; responses: request.tools non-empty); the rest are housekeeping calls
(OpenCode session titles and the like) and are counted apart.

Three wire formats, chosen by record path:
  (a) /api/v1/messages          Anthropic messages (Claude Code)
  (b) /api/v1/responses         OpenAI responses (Codex, wire_api = "responses")
  (c) /api/v1/chat/completions  chat completions (OpenCode, Pi)
turns = number of agent records; tool_calls = tool_use / function_call / tool_calls items across the history plus the
final response; tokens summed over agent records; model_ids from every response; mismatch = agent records whose model
id differs from the pin.
Records come from proxy.load_records (req/resp pairs joined; perceive.py marks unparseable files with `_bad`). A record
carrying `_bad` sets parse_error='bad-record:<id>' and is left out of the history (the run is flagged, not scored on a
partial history); an agent record whose response never arrived (`resp_missing`) sets 'missing-response:<id>'.
Content blocks, messages or usage values of an unexpected shape are skipped and counted (Perception.skipped_blocks)
with parse_error='malformed:<what>' rather than crashing the parse.
"""
import json
import re
from perception import Perception, ToolEvent, add_error, classify_tool, finalize, to_int

PATH_KIND = (("/messages", "anthropic"), ("/responses", "responses"), ("/chat/completions", "chat"))
MODEL_RE = re.compile(r'"model"\s*:\s*"([^"]+)"')


def _kind(path: str) -> str:
    path = path if isinstance(path, str) else ""
    for suffix, k in PATH_KIND:
        if path.split("?")[0].rstrip("/").endswith(suffix):
            return k
    return "unknown"


def _sse_json(text: str):
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            yield json.loads(payload)
        except Exception:
            continue


def _is_agent(rec: dict) -> bool:
    req = rec.get("request")
    return isinstance(req, dict) and bool(req.get("tools"))


def _skip(p: Perception, what: str) -> None:
    """A block/message/usage value of an unexpected shape: count it and name it once in parse_error."""
    p.skipped_blocks += 1
    if f"malformed:{what}" not in (p.parse_error or "").split(";"):
        add_error(p, f"malformed:{what}")


def _num(p: Perception, v, what: str) -> int:
    n = to_int(v)
    if n is None:
        _skip(p, what); return 0
    return n


def _dicts(p: Perception, seq, what: str) -> list[dict]:
    """The dict items of a list; a non-list (other than None) or non-dict items are skipped and named."""
    if seq is None:
        return []
    if isinstance(seq, dict):
        seq = [seq]
    if not isinstance(seq, list):
        _skip(p, what); return []
    out = []
    for x in seq:
        if isinstance(x, dict):
            out.append(x)
        else:
            _skip(p, what)
    return out


def _path_of(args) -> str:
    if isinstance(args, dict):
        for k in ("file_path", "path", "filePath", "filename", "file", "target_file", "notebook_path"):
            if isinstance(args.get(k), str):
                return args[k]
        cmd = args.get("command") or args.get("cmd")
        if isinstance(cmd, str):
            return ""
    return ""


def _args_text(args) -> str:
    if isinstance(args, str):
        return args
    try:
        return json.dumps(args, ensure_ascii=False)
    except Exception:
        return str(args)


def _tool_event(turn: int, name: str, args, result_text: str = "") -> ToolEvent:
    at = _args_text(args)
    return ToolEvent(turn=turn, name=name or "", kind=classify_tool(name or "", at), path=_path_of(args),
                     args_text=at, result_text=result_text or "")


def _content_text(c) -> str:
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in c)
    if c is None:
        return ""
    return str(c)


# ---- (a) Anthropic messages ---------------------------------------------------------------------------------------

def _history_anthropic(req: dict, p: Perception):
    turn = 0; pending: dict[str, ToolEvent] = {}
    for m in _dicts(p, req.get("messages"), "anthropic.message"):
        content = m.get("content")
        if m.get("role") == "assistant":
            turn += 1
            if isinstance(content, str):
                if content.strip():
                    p.assistant_texts.append(content)
                continue
            for b in _dicts(p, content, "anthropic.content-block"):
                if b.get("type") == "text" and isinstance(b.get("text"), str) and b["text"].strip():
                    p.assistant_texts.append(b["text"])
                elif b.get("type") == "tool_use":
                    ev = _tool_event(turn, b.get("name"), b.get("input"))
                    p.tool_events.append(ev); pending[str(b.get("id", ""))] = ev
        elif m.get("role") == "user" and isinstance(content, list):
            for b in _dicts(p, content, "anthropic.content-block"):
                if b.get("type") == "tool_result":
                    ev = pending.get(str(b.get("tool_use_id", "")))
                    if ev is not None:
                        ev.result_text = _content_text(b.get("content"))
    return turn


def _response_anthropic(text: str, p: Perception, turn: int) -> tuple[str, list[str]]:
    final = []; models = []; cur_tool = None; cur_json = []
    for ev in _sse_json(text):
        if not isinstance(ev, dict):
            _skip(p, "anthropic.sse-event"); continue
        t = ev.get("type")
        if t == "message_start":
            msg = ev.get("message") if isinstance(ev.get("message"), dict) else {}
            models.append(str(msg.get("model") or ""))
            u = msg.get("usage") if isinstance(msg.get("usage"), dict) else {}
            p.tokens_in += _num(p, u.get("input_tokens"), "anthropic.usage")
        elif t == "content_block_start":
            cb = ev.get("content_block") if isinstance(ev.get("content_block"), dict) else {}
            if cb.get("type") == "tool_use":
                cur_tool = cb.get("name"); cur_json = []
        elif t == "content_block_delta":
            d = ev.get("delta") if isinstance(ev.get("delta"), dict) else {}
            if d.get("type") == "text_delta":
                final.append(str(d.get("text") or ""))
            elif d.get("type") == "input_json_delta":
                cur_json.append(str(d.get("partial_json") or ""))
        elif t == "content_block_stop":
            if cur_tool is not None:
                raw = "".join(cur_json)
                try:
                    args = json.loads(raw) if raw else {}
                except Exception:
                    args = raw
                p.tool_events.append(_tool_event(turn, cur_tool, args)); cur_tool = None
        elif t == "message_delta":
            u = ev.get("usage") if isinstance(ev.get("usage"), dict) else {}
            p.tokens_out += _num(p, u.get("output_tokens"), "anthropic.usage")
    return "".join(final), [m for m in models if m]


def _params_anthropic(req: dict, p: Perception):
    p.temperature = _s(req.get("temperature")); p.top_p = _s(req.get("top_p")); p.max_tokens = _s(req.get("max_tokens"))
    th = req.get("thinking")
    if isinstance(th, dict):
        p.reasoning_effort = _s(th.get("type") if th.get("type") != "enabled" else th.get("budget_tokens", "enabled"))


# ---- (b) OpenAI responses -----------------------------------------------------------------------------------------

def _history_responses(req: dict, p: Perception):
    turn = 0; after_output = True; pending: dict[str, ToolEvent] = {}
    for item in _dicts(p, req.get("input"), "responses.input-item"):
        t = item.get("type", "message")
        if t == "message" and item.get("role") == "assistant":
            if after_output:
                turn += 1; after_output = False
            content = item.get("content")
            if isinstance(content, str):
                txt = content
            else:
                txt = "\n".join(str(c.get("text") or "") for c in _dicts(p, content, "responses.content-block")
                                if c.get("type") in ("output_text", "input_text", "text"))
            if txt.strip():
                p.assistant_texts.append(txt)
        elif t == "function_call":
            if after_output:
                turn += 1; after_output = False
            args = item.get("arguments")
            try:
                args = json.loads(args) if isinstance(args, str) else args
            except Exception:
                pass
            ev = _tool_event(turn, item.get("name"), args); p.tool_events.append(ev); pending[str(item.get("call_id", ""))] = ev
        elif t == "function_call_output":
            after_output = True
            ev = pending.get(str(item.get("call_id", "")))
            if ev is not None:
                ev.result_text = _content_text(item.get("output"))
    return turn


def _response_responses(text: str, p: Perception, turn: int) -> tuple[str, list[str]]:
    final = []; models = []
    for ev in _sse_json(text):
        if not isinstance(ev, dict):
            _skip(p, "responses.sse-event"); continue
        t = ev.get("type", "")
        r0 = ev.get("response") if isinstance(ev.get("response"), dict) else {}
        if t == "response.created":
            models.append(str(r0.get("model") or ""))
        elif t == "response.output_text.delta":
            final.append(str(ev.get("delta") or ""))
        elif t == "response.output_item.done":
            item = ev.get("item") if isinstance(ev.get("item"), dict) else {}
            if item.get("type") == "function_call":
                args = item.get("arguments")
                try:
                    args = json.loads(args) if isinstance(args, str) else args
                except Exception:
                    pass
                p.tool_events.append(_tool_event(turn, item.get("name"), args))
        elif t == "response.completed":
            u = r0.get("usage") if isinstance(r0.get("usage"), dict) else {}
            p.tokens_in += _num(p, u.get("input_tokens"), "responses.usage"); p.tokens_out += _num(p, u.get("output_tokens"), "responses.usage")
            det = u.get("output_tokens_details") if isinstance(u.get("output_tokens_details"), dict) else {}
            p.tokens_reasoning += _num(p, det.get("reasoning_tokens"), "responses.usage")
            models.append(str(r0.get("model") or ""))
    return "".join(final), [m for m in models if m]


def _params_responses(req: dict, p: Perception):
    p.temperature = _s(req.get("temperature")); p.top_p = _s(req.get("top_p")); p.max_tokens = _s(req.get("max_output_tokens"))
    r = req.get("reasoning")
    if isinstance(r, dict):
        p.reasoning_effort = _s(r.get("effort"))


# ---- (c) chat completions -----------------------------------------------------------------------------------------

def _history_chat(req: dict, p: Perception):
    turn = 0; pending: dict[str, ToolEvent] = {}
    for m in _dicts(p, req.get("messages"), "chat.message"):
        role = m.get("role")
        if role == "assistant":
            turn += 1
            txt = _content_text(m.get("content"))
            if txt.strip():
                p.assistant_texts.append(txt)
            for tc in _dicts(p, m.get("tool_calls"), "chat.tool-call"):
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                args = fn.get("arguments")
                try:
                    args = json.loads(args) if isinstance(args, str) else args
                except Exception:
                    pass
                ev = _tool_event(turn, fn.get("name"), args); p.tool_events.append(ev); pending[str(tc.get("id", ""))] = ev
        elif role == "tool":
            ev = pending.get(str(m.get("tool_call_id", "")))
            if ev is not None:
                ev.result_text = _content_text(m.get("content"))
    return turn


def _response_chat(text: str, p: Perception, turn: int) -> tuple[str, list[str]]:
    final = []; models = []; calls: dict[int, dict] = {}
    for ch in _sse_json(text):
        if not isinstance(ch, dict):
            _skip(p, "chat.sse-event"); continue
        if ch.get("model"):
            models.append(str(ch["model"]))
        for choice in _dicts(p, ch.get("choices"), "chat.choice"):
            d = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
            if isinstance(d.get("content"), str) and d["content"]:
                final.append(d["content"])
            for tc in _dicts(p, d.get("tool_calls"), "chat.tool-call"):
                idx = to_int(tc.get("index")) or 0; slot = calls.setdefault(idx, {"name": "", "args": ""})
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                slot["name"] = str(fn.get("name") or slot["name"]); slot["args"] += str(fn.get("arguments") or "")
        u = ch.get("usage")
        if isinstance(u, dict):
            p.tokens_in += _num(p, u.get("prompt_tokens"), "chat.usage"); p.tokens_out += _num(p, u.get("completion_tokens"), "chat.usage")
            det = u.get("completion_tokens_details") if isinstance(u.get("completion_tokens_details"), dict) else {}
            p.tokens_reasoning += _num(p, det.get("reasoning_tokens"), "chat.usage")
    for idx in sorted(calls):
        raw = calls[idx]["args"]
        try:
            args = json.loads(raw) if raw else {}
        except Exception:
            args = raw
        p.tool_events.append(_tool_event(turn, calls[idx]["name"], args))
    return "".join(final), list(dict.fromkeys(m for m in models if m))


def _params_chat(req: dict, p: Perception):
    p.temperature = _s(req.get("temperature")); p.top_p = _s(req.get("top_p")); p.max_tokens = _s(req.get("max_tokens"))
    r = req.get("reasoning")
    p.reasoning_effort = _s(r.get("effort") if isinstance(r, dict) else req.get("reasoning_effort"))


def _s(v) -> str:
    return "" if v is None else str(v)


FORMATS = {"anthropic": (_history_anthropic, _response_anthropic, _params_anthropic),
           "responses": (_history_responses, _response_responses, _params_responses),
           "chat": (_history_chat, _response_chat, _params_chat)}


def _usage_only(rec: dict, kind: str, p: Perception):
    """Token and model bookkeeping for the agent records that are not the last one."""
    scratch = Perception()
    rt = rec.get("response_text")
    _, models = FORMATS[kind][1](rt if isinstance(rt, str) else "", scratch, 0)
    p.tokens_in += scratch.tokens_in; p.tokens_out += scratch.tokens_out; p.tokens_reasoning += scratch.tokens_reasoning
    p.skipped_blocks += scratch.skipped_blocks
    if scratch.parse_error:
        for tag in scratch.parse_error.split(";"):
            if tag not in (p.parse_error or "").split(";"):
                add_error(p, tag)
    return models


def parse_run(records: list[dict], conflict: dict, pin: str) -> Perception:
    p = Perception(source="proxy")
    records = [r for r in records if isinstance(r, dict)]
    bad = [str(r.get("id") or "?") for r in records if r.get("_bad")]
    if bad:
        add_error(p, "bad-record:" + ",".join(bad))
        records = [r for r in records if not r.get("_bad")]
    records = sorted(records, key=lambda r: (r.get("ts") or 0, str(r.get("id", ""))))
    agent = [r for r in records if _is_agent(r)]
    p.housekeeping_calls = len(records) - len(agent)
    missing = [str(r.get("id") or "?") for r in agent if r.get("resp_missing")]
    if missing:
        add_error(p, "missing-response:" + ",".join(missing))
    if not agent:
        add_error(p, "no-agent-records"); return finalize(p, conflict, pin)
    p.turns = len(agent)
    for r in agent:
        p.proxy_empty_retries += len(r.get("empty_attempts") or [])
        rt = r.get("response_text") if isinstance(r.get("response_text"), str) else ""
        if _kind(r.get("path", "")) == "anthropic" and r.get("status") == 200 and rt and "content_block_start" not in rt:
            p.empty_replies += 1
            if r is agent[-1]:
                p.ended_on_empty = True
    all_models: list[str] = []; mismatches = 0
    kinds = {_kind(r.get("path", "")) for r in agent}
    kinds.discard("unknown")
    if len(kinds) > 1:
        add_error(p, f"mixed-formats:{','.join(sorted(kinds))}")
    for r in agent[:-1]:
        k = _kind(r.get("path", ""))
        if k == "unknown":
            continue
        ms = _usage_only(r, k, p)
        all_models += ms
        if ms and any(m != pin for m in ms):
            mismatches += 1
        elif not ms:
            m = MODEL_RE.search(r.get("response_text") if isinstance(r.get("response_text"), str) else "")
            if m:
                all_models.append(m.group(1)); mismatches += int(m.group(1) != pin)
    last = agent[-1]; k = _kind(last.get("path", ""))
    if k == "unknown":
        add_error(p, f"unknown-path:{last.get('path')}")
        return finalize(p, conflict, pin)
    hist, resp, params = FORMATS[k]
    req = last.get("request")   # a dict: _is_agent checked it
    turn = hist(req, p)
    params(req, p)
    rt = last.get("response_text")
    final, ms = resp(rt if isinstance(rt, str) else "", p, turn + 1)
    all_models += ms
    if ms and any(m != pin for m in ms):
        mismatches += 1
    p.final_message = final
    if final.strip():
        p.assistant_texts.append(final)
    p.model_ids = ";".join(dict.fromkeys(all_models))
    p.model_mismatch_count = mismatches
    return finalize(p, conflict, pin)
