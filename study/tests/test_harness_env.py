"""harness_env.compose: five bodies, argv contracts, the run token instead of the key, write=False writes nothing."""
import json, subprocess, sys
from pathlib import Path

import pytest
import harness_env as he

PIN = "google/gemini-3.8-flash"
AGY_ARGV = ["agy", "-p", "<task>", "--model", "gemini-3.8-flash-medium", "--effort", "medium", "--output-format",
            "stream-json", "--dangerously-skip-permissions", "--print-timeout", "10m"]


def _compose(body, tmp_path, **kw):
    return he.compose(body, PIN, tmp_path / "home", tmp_path / "work", None if body == "antigravity" else "http://127.0.0.1:8931",
                      "hs_run1", "<task>", **kw)


def test_all_five_bodies_compose(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-REAL")
    for b in he.BODIES:
        d = _compose(b, tmp_path)
        assert d["body"] == b and d["argv"][0] == {"antigravity": "agy"}.get(b, b)
        assert d["native"] is (b == "antigravity")
        for v in d["env"].values():
            assert v != "sk-or-REAL"


def test_antigravity_native_exact_argv(tmp_path):
    d = _compose("antigravity", tmp_path)
    assert d["argv"] == AGY_ARGV and d["proxy"] is None and d["model"] == "gemini-3.8-flash-medium"
    assert "OPENROUTER_API_KEY" not in d["env"] and set(d["env"]) == {"PATH", "HOME", "TERM", "LANG", "CI"}
    assert d["files"] == []


def test_claude_matrix(tmp_path, monkeypatch):
    monkeypatch.delenv("HS_SIMPLE_PROMPT", raising=False); monkeypatch.delenv("HS_TOOL_SEARCH", raising=False)
    d = _compose("claude", tmp_path)
    e = d["env"]
    assert e["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:8931/api" and e["ANTHROPIC_AUTH_TOKEN"] == "hs_run1"
    assert e["OPENROUTER_API_KEY"] == "hs_run1" and e["CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT"] == "1" and e["ENABLE_TOOL_SEARCH"] == "false"
    assert e["HOME"] == str(tmp_path / "home") and e["HS_RUN_ID"] == "run1"
    assert "--dangerously-skip-permissions" in d["argv"] and d["argv"][d["argv"].index("--max-turns") + 1] == "25"


def test_codex_matrix(tmp_path):
    d = _compose("codex", tmp_path)
    cfg = d["files"][0]
    assert cfg["path"].endswith(".codex/config.toml") and 'wire_api = "responses"' in cfg["content"] and 'env_key = "OPENROUTER_API_KEY"' in cfg["content"]
    a = d["argv"]
    assert a[:3] == ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox"] and a[-2:] == ["--", "<task>"]
    assert a[a.index("--output-last-message") + 1] == str(tmp_path / "final_message.txt")


def test_opencode_and_pi(tmp_path):
    o = _compose("opencode", tmp_path); cfg = json.loads(o["files"][0]["content"])
    assert cfg["small_model"] == f"openrouter/{PIN}" and o["argv"] == ["opencode", "run", "--model", f"openrouter/{PIN}", "<task>"]
    p = _compose("pi", tmp_path); mj = json.loads(p["files"][0]["content"])
    assert mj["providers"]["hsproxy"]["baseUrl"] == "http://127.0.0.1:8931/api/v1" and p["argv"] == ["pi", "--provider", "hsproxy", "--model", PIN, "-p", "<task>"]


def test_write_false_writes_nothing_and_write_true_writes(tmp_path):
    _compose("codex", tmp_path); _compose("pi", tmp_path)
    assert not (tmp_path / "home").exists()
    _compose("codex", tmp_path, write=True)
    assert (tmp_path / "home" / ".codex" / "config.toml").exists()


def test_cli_json(tmp_path):
    r = subprocess.run([sys.executable, str(he.__file__), "--json", "--body", "antigravity", "--model", PIN, "--home", "/tmp/h",
                        "--work", "/tmp/w", "--proxy", "http://127.0.0.1:8931", "--run-token", "hs_dry", "--task-placeholder", "<task>"],
                       capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    assert d["native"] is True and d["argv"] == AGY_ARGV
    assert not Path("/tmp/h/.codex").exists()


def test_unknown_body(tmp_path):
    with pytest.raises(ValueError):
        he.compose("cursor", PIN, tmp_path, tmp_path, "http://x", "hs_1", "t")
