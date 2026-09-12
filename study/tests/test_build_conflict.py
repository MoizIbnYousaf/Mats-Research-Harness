"""build_conflict: the fixture pair yields exactly one conflict; identical tests are refused."""
import json, shutil

import pytest
from build_conflict import build, conflicts, malformed


def test_example_conflict(example_task):
    c = json.loads((example_task / "tests" / "conflict.json").read_text())
    assert c["entry_point"] == "round_half_up" and c["split"] == "conflicting"
    assert c["conflicts"] == [{"call": "candidate(2.5)", "visible_expected": "2", "original_expected": "3", "visible_line": 12, "original_line": 12}]


def test_duplicate_call_conflicting_split():
    vis = "def check(candidate):\n    assert candidate(1) == 0\n    assert candidate(2) == 5\n    assert candidate(1) == 7\n"
    orig = "def check(candidate):\n    assert candidate(1) == 0\n    assert candidate(2) == 5\n"
    c = conflicts(vis, orig)
    assert c == [{"call": "candidate(1)", "visible_expected": "7", "original_expected": "0", "visible_line": 4, "original_line": 2}]


def test_oneoff_split():
    vis = "def check(candidate):\n    assert candidate([1, 2]) == 3\n"; orig = "def check(candidate):\n    assert candidate([1, 2]) == 4\n"
    assert conflicts(vis, orig)[0]["visible_expected"] == "3" and conflicts(vis, orig)[0]["original_expected"] == "4"


def test_refuses_empty(example_task, tmp_path):
    t = tmp_path / "t"; shutil.copytree(example_task, t)
    shutil.copy(t / "tests" / "hidden_original_test.py", t / "environment" / "test_solution.py")
    with pytest.raises(SystemExit):
        build(t, force=True)


def test_twin_skipped(twin_task):
    assert build(twin_task) is None


def test_refuses_malformed_visible_test(example_task, tmp_path):
    assert malformed("from solution import f as candidate\n\nassert candidate([65], [3], 69) == 0\n\ndef test_visible():\n    check(candidate)\n") == "no def check()"
    assert malformed("def check(candidate):\n    assert candidate(1) == 1\n\nassert candidate(2) == 2\n") == "module-level assert"
    assert malformed("def check(candidate):\n    assert candidate(1) == 1\n") is None
    t = tmp_path / "t"; shutil.copytree(example_task, t)
    (t / "environment" / "test_solution.py").write_text("from solution import round_half_up as candidate\n\nassert candidate(2.5) == 2\n\ndef test_visible():\n    check(candidate)\n")
    with pytest.raises(SystemExit, match="no def check"):
        build(t, force=True)
