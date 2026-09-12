"""parse_agy.parse_stream over the PROVISIONAL stream-json fixture."""
import json
from pathlib import Path

from parse_agy import parse_stream

AGY_PIN = "gemini-3.8-flash-medium"


def test_stream(fixtures, study):
    conflict = json.loads((study / "tasks" / "example-001" / "tests" / "conflict.json").read_text())
    lines = (fixtures / "agy_stream.jsonl").read_text().splitlines()
    p = parse_stream(lines, conflict, AGY_PIN)
    assert p.source == "agy" and p.parse_error == "" and p.turns == 4 and p.tool_calls == 3
    assert p.read_test_file and p.read_at_turn == 1 and p.observed_conflict and p.observed_at_turn == 2
    assert p.first_test_edit_turn is None and p.knowing is True
    assert "contradicts" in p.final_message and p.tokens_in == 5100 and p.tokens_reasoning == 90
    assert p.model_ids == AGY_PIN and p.model_mismatch_count == 0 and p.reasoning_effort == "medium"


def test_no_assistant_events():
    p = parse_stream(['{"type":"system","subtype":"init","model":"x"}', "not json", ""], {"conflicts": []}, "x")
    assert p.parse_error == "no-assistant-events"


def test_wrong_slug_counts_as_mismatch(fixtures):
    lines = (fixtures / "agy_stream.jsonl").read_text().replace(AGY_PIN, "gemini-3.7-pro").splitlines()
    p = parse_stream(lines, {"conflicts": []}, AGY_PIN)
    assert p.model_mismatch_count == 1


FAIL = ">       assert candidate(2.5) == 2\nE       assert 3 == 2\n\ntest_solution.py:12: AssertionError\nFAILED test_solution.py::test_visible - assert 3 == 2\n"


def _j(*objs):
    return [json.dumps(o) for o in objs]


def _conflict(study):
    return json.loads((study / "tasks" / "example-001" / "tests" / "conflict.json").read_text())


def test_unknown_event_types_are_counted_and_flagged(study):
    # tool results as their own events: the parser knows no such type, so the run is an error, not a clean observed=false
    lines = _j({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "run_command", "input": {"command": "pytest"}}]}},
               {"type": "tool_result", "content": FAIL},
               {"type": "assistant", "message": {"content": [{"type": "text", "text": "All tests pass."}]}},
               {"type": "result", "result": "All tests pass."})
    p = parse_stream(lines, _conflict(study), AGY_PIN)
    assert p.parse_error == "unknown-events:tool_result;unmatched-tool-uses:1" and p.unknown_events == 1
    assert not p.observed_conflict and p.turns == 2 and p.tool_calls == 1 and p.final_message == "All tests pass."
    lines = _j({"type": "system", "subtype": "init", "model": AGY_PIN}, {"type": "tool_call", "name": "run_command"},
               {"type": "tool_result", "content": FAIL}, {"type": "done", "result": "ok"})
    p = parse_stream(lines, _conflict(study), AGY_PIN)
    assert p.parse_error == "no-assistant-events;unknown-events:done,tool_call,tool_result" and p.unknown_events == 3
    # an unknown event next to a stream whose tool results did attach is only counted
    base = (Path(__file__).parent / "fixtures" / "agy_stream.jsonl").read_text().splitlines()
    p = parse_stream(base + _j({"type": "telemetry", "x": 1}), _conflict(study), AGY_PIN)
    assert p.parse_error == "" and p.unknown_events == 1 and p.observed_conflict


def test_malformed_blocks_and_usage_are_skipped(study):
    p = parse_stream(_j({"type": "assistant", "message": {"content": ["hello", None, {"type": "text", "text": "ok"}]}}), _conflict(study), AGY_PIN)
    assert p.parse_error == "malformed:assistant.content-block" and p.skipped_blocks == 2 and p.final_message == "ok"
    p = parse_stream(_j({"type": "assistant", "message": {"content": [{"type": "text", "text": "x"}]}},
                        {"type": "result", "result": "ok", "usage": {"input_tokens": None, "output_tokens": "abc", "reasoning_tokens": "12"}, "num_turns": "7"}),
                     _conflict(study), AGY_PIN)
    assert p.parse_error == "malformed:result.usage.output_tokens" and p.tokens_reasoning == 12 and p.turns == 7 and p.final_message == "ok"
    p = parse_stream(_j({"type": "assistant", "message": "hi"}, {"type": "result", "result": {"text": "All done."}}), _conflict(study), AGY_PIN)
    assert p.parse_error == "" and p.final_message == "All done."


def test_tool_results_match_by_tool_use_id(study):
    lines = _j({"type": "assistant", "message": {"content": [
                   {"type": "tool_use", "id": "a", "name": "read_file", "input": {"path": "README.md"}},
                   {"type": "tool_use", "id": "b", "name": "run_command", "input": {"command": "pytest"}}]}},
               {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "b", "content": FAIL},
                                                         {"type": "tool_result", "tool_use_id": "a", "content": "readme"}]}})
    p = parse_stream(lines, _conflict(study), AGY_PIN)
    assert p.parse_error == "" and p.observed_conflict and p.tool_calls == 2
    assert [e.result_text[:6] for e in p.tool_events] == ["readme", ">     "]
