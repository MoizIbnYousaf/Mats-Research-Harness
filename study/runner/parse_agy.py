#!/usr/bin/env python3
"""Antigravity stream-json parser -> Perception (PLAN v3 lines 26, 30: Antigravity is vendor-native and its
stream-json is the record). One JSON object per line on stdout.

EVENT NAMES ARE PROVISIONAL until the first real capture. At hour zero run
    agy -p 'say hello' --model gemini-3.8-flash-medium --output-format stream-json
and diff the lines against tests/fixtures/agy_stream.jsonl; fix the field names here and in the fixture, then re-run
the tests. The shape assumed (Claude-Code-like, which is what the Antigravity docs describe):
  {"type":"system","subtype":"init","model":...}
  {"type":"assistant","message":{"content":[{"type":"text","text":...},{"type":"tool_use","name":...,"input":{...}}]}}
  {"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":?,"content":...}]}}
  {"type":"result","result":str,"usage":{"input_tokens","output_tokens","reasoning_tokens"},"num_turns":int,"model":...}
Unknown event types are counted (Perception.unknown_events); when the stream has unknown types and not one tool
result was attached to a tool_use, parse_error='unknown-events:<types>' (the tool results are probably their own
events, which this parser does not know). A tool_use left without a result while unknown events exist adds
'unmatched-tool-uses:N'. No assistant event at all -> parse_error='no-assistant-events'. Content blocks or usage
values of an unexpected shape are skipped and counted (skipped_blocks) with parse_error='malformed:<what>'.
model_ids come from init and result; the pin to compare against is the agy model slug (gemini-3.8-flash-medium).
"""
import json
from perception import Perception, ToolEvent, add_error, classify_tool, finalize, to_int

KNOWN_TYPES = {"system", "assistant", "user", "result"}


def _args_text(args) -> str:
    if isinstance(args, str):
        return args
    try:
        return json.dumps(args, ensure_ascii=False)
    except Exception:
        return str(args)


def _path_of(args) -> str:
    if isinstance(args, dict):
        for k in ("file_path", "path", "filePath", "filename", "file", "target_file"):
            if isinstance(args.get(k), str):
                return args[k]
    return ""


def _content_text(c) -> str:
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in c)
    return "" if c is None else str(c)


def _usage(p: Perception, u, malformed: list[str], where: str) -> dict[str, int]:
    """Tolerant usage read: {"input_tokens": n, "output_tokens": n, "reasoning_tokens": n}; bad values are 0 and named."""
    out = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
    if u is None:
        return out
    if not isinstance(u, dict):
        malformed.append(f"{where}.usage"); p.skipped_blocks += 1
        return out
    for k, alts in (("input_tokens", ()), ("output_tokens", ()), ("reasoning_tokens", ("thoughts_tokens",))):
        v = u.get(k)
        for a in alts:
            if v is None:
                v = u.get(a)
        n = to_int(v)
        if n is None:
            malformed.append(f"{where}.usage.{k}"); p.skipped_blocks += 1; n = 0
        out[k] = n
    return out


def parse_stream(lines, conflict: dict, pin: str) -> Perception:
    p = Perception(source="agy")
    models: list[str] = []; turn = 0; seen_assistant = False; result_text = None
    pending: list[ToolEvent] = []; by_id: dict[str, ToolEvent] = {}
    usage: dict[str, int] = {}; num_turns = None; unknown: dict[str, int] = {}; malformed: list[str] = []
    results_attached = 0
    for raw in lines:
        raw = raw.strip()
        if not raw or not raw.startswith("{"):
            continue
        try:
            ev = json.loads(raw)
        except Exception:
            continue
        if not isinstance(ev, dict):
            continue
        t = ev.get("type")
        if t == "system":
            if ev.get("model"):
                models.append(str(ev["model"]))
            if ev.get("subtype") == "init":
                for k in ("temperature", "top_p", "max_tokens"):
                    if ev.get(k) is not None:
                        setattr(p, k, str(ev[k]))
                if ev.get("effort") or ev.get("reasoning_effort"):
                    p.reasoning_effort = str(ev.get("effort") or ev.get("reasoning_effort"))
        elif t == "assistant":
            seen_assistant = True; turn += 1
            msg = ev.get("message")
            if isinstance(msg, str):
                if msg.strip():
                    p.assistant_texts.append(msg)
                continue
            if not isinstance(msg, dict):
                malformed.append("assistant.message"); p.skipped_blocks += 1
                continue
            if msg.get("model"):
                models.append(str(msg["model"]))
            u = _usage(p, msg.get("usage"), malformed, "assistant")
            p.tokens_in += u["input_tokens"]; p.tokens_out += u["output_tokens"]; p.tokens_reasoning += u["reasoning_tokens"]
            content = msg.get("content")
            if isinstance(content, str):
                if content.strip():
                    p.assistant_texts.append(content)
                continue
            if content is not None and not isinstance(content, list):
                malformed.append("assistant.content"); p.skipped_blocks += 1
                continue
            for b in content or []:
                if not isinstance(b, dict):
                    malformed.append("assistant.content-block"); p.skipped_blocks += 1
                    continue
                if b.get("type") == "text" and isinstance(b.get("text"), str) and b["text"].strip():
                    p.assistant_texts.append(b["text"])
                elif b.get("type") == "tool_use":
                    at = _args_text(b.get("input"))
                    e = ToolEvent(turn=turn, name=str(b.get("name") or ""), kind=classify_tool(str(b.get("name") or ""), at),
                                  path=_path_of(b.get("input")), args_text=at)
                    p.tool_events.append(e); pending.append(e)
                    if isinstance(b.get("id"), str):
                        by_id[b["id"]] = e
        elif t == "user":
            msg = ev.get("message")
            content = msg.get("content") if isinstance(msg, dict) else None
            if content is not None and not isinstance(content, list):
                malformed.append("user.content"); p.skipped_blocks += 1
                continue
            for b in content or []:
                if not isinstance(b, dict):
                    malformed.append("user.content-block"); p.skipped_blocks += 1
                    continue
                if b.get("type") != "tool_result":
                    continue
                e = by_id.get(b.get("tool_use_id")) if isinstance(b.get("tool_use_id"), str) else None
                if e is not None and e in pending:
                    pending.remove(e)
                elif pending:
                    e = pending.pop(0)
                else:
                    e = None
                if e is not None:
                    e.result_text = _content_text(b.get("content")); results_attached += 1
        elif t == "result":
            r = ev.get("result")
            result_text = r if isinstance(r, str) else (_content_text(r.get("text") or r.get("content")) if isinstance(r, dict) else None)
            usage = _usage(p, ev.get("usage"), malformed, "result") if ev.get("usage") is not None else {}
            num_turns = to_int(ev.get("num_turns")) if ev.get("num_turns") is not None else None
            if ev.get("model"):
                models.append(str(ev["model"]))
        else:
            key = str(t) if t is not None else "<missing>"
            unknown[key] = unknown.get(key, 0) + 1
    p.unknown_events = sum(unknown.values())
    if not seen_assistant:
        add_error(p, "no-assistant-events")
    if unknown and results_attached == 0:
        add_error(p, "unknown-events:" + ",".join(sorted(unknown)))
    if unknown and pending:
        add_error(p, f"unmatched-tool-uses:{len(pending)}")
    if malformed:
        add_error(p, "malformed:" + ",".join(dict.fromkeys(malformed)))
    if usage:
        # the result usage is the run total; prefer it over per-message sums when present
        p.tokens_in = usage["input_tokens"] or p.tokens_in; p.tokens_out = usage["output_tokens"] or p.tokens_out
        p.tokens_reasoning = usage["reasoning_tokens"] or p.tokens_reasoning
    p.turns = num_turns if isinstance(num_turns, int) and num_turns > 0 else turn
    p.final_message = result_text if isinstance(result_text, str) else (p.assistant_texts[-1] if p.assistant_texts else "")
    if isinstance(result_text, str) and result_text.strip() and (not p.assistant_texts or p.assistant_texts[-1] != result_text):
        p.assistant_texts.append(result_text)
    uniq = list(dict.fromkeys(m for m in models if m))
    p.model_ids = ";".join(uniq)
    p.model_mismatch_count = sum(1 for m in uniq if pin and m != pin)
    return finalize(p, conflict, pin)
