#!/usr/bin/env python3
"""Launch composition for the five bodies (PLAN v3 line 26). One source for run.py, batch.py and `mrh dump`/`mrh watch`.

Four routable bodies (claude, codex, opencode, pi) reach OpenRouter through the local logging proxy with the model
pinned; they never hold the real key, only a run token `hs_<run_id>` which the proxy swaps for the key (proxy.py).
Antigravity (`agy`) is vendor-native: Google sign-in, account quota, not proxy-routable; its stream-json is the record.
Matrices for claude/codex/opencode/pi were verified against the proxy log on this machine (confound notes section 9).

CLI: harness_env.py --json --body B --model M --home H --work W --proxy P --run-token T
                    [--task-file F | --task-placeholder '<task>'] [--write]
"""
import argparse, json, os, sys
from pathlib import Path

BODIES = ("antigravity", "claude", "codex", "opencode", "pi")
NATIVE = {"antigravity"}
EFFORT = os.environ.get("HS_EFFORT", "")  # empty: each body's own default (Codex medium); "medium": --effort / model_reasoning_effort / --variant / --thinking
AGY_MODEL_DEFAULT = "gemini-3.8-flash-medium"
AGY_EFFORT_DEFAULT = "medium"


def _base_env(home: Path, run_token: str) -> dict:
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home), "TERM": "xterm", "LANG": "C.UTF-8",
            "CI": "1", "HS_RUN_ID": run_token[3:] if run_token.startswith("hs_") else run_token}


def compose(body: str, model: str, home: Path, work: Path, proxy: str | None, run_token: str, task: str, *,
            max_turns: int = 25, agy_model: str = AGY_MODEL_DEFAULT, effort: str = AGY_EFFORT_DEFAULT,
            system_prompt: str | None = None, write: bool = False) -> dict:
    """Return {body, native, proxy, model, argv, env, files:[{path, content}]}. Files are written only when write=True."""
    home = Path(home); work = Path(work)
    files: list[dict] = []
    if body == "antigravity":
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "HOME": os.environ.get("HS_AGY_HOME") or os.environ.get("HOME", str(Path.home())),
               "TERM": "xterm", "LANG": "C.UTF-8", "CI": "1"}
        argv = ["agy", "-p", task, "--model", agy_model, "--effort", effort, "--output-format", "stream-json",
                "--dangerously-skip-permissions", "--print-timeout", "10m"]
        return {"body": body, "native": True, "proxy": None, "model": agy_model, "argv": argv, "env": env, "files": files}
    if proxy is None:
        raise ValueError(f"{body} needs a proxy URL (only antigravity is native)")
    base = _base_env(home, run_token)
    base["OPENROUTER_API_KEY"] = run_token
    if body == "claude":
        env = dict(base, CLAUDE_CONFIG_DIR=str(home / ".claude"), ANTHROPIC_BASE_URL=f"{proxy}/api",
                   ANTHROPIC_AUTH_TOKEN=run_token, ANTHROPIC_API_KEY="",
                   CLAUDE_CODE_SKIP_FAST_MODE_ORG_CHECK="1", CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY="1",
                   ENABLE_TOOL_SEARCH=os.environ.get("HS_TOOL_SEARCH", "false"),
                   CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT=os.environ.get("HS_SIMPLE_PROMPT", "1"),
                   ANTHROPIC_MODEL=model, ANTHROPIC_DEFAULT_SONNET_MODEL=model, ANTHROPIC_DEFAULT_OPUS_MODEL=model,
                   ANTHROPIC_DEFAULT_HAIKU_MODEL=model, ANTHROPIC_DEFAULT_FABLE_MODEL=model)
        argv = ["claude", "--model", model, "-p", task, "--output-format", "stream-json", "--verbose",
                "--dangerously-skip-permissions", "--max-turns", str(max_turns)]
        if EFFORT:
            argv += ["--effort", EFFORT]  # HS_EFFORT: equal reasoning effort across bodies (Ori's mapping; LOG Sept 4 06:35)
        if system_prompt is not None:
            argv += ["--system-prompt", system_prompt, "--exclude-dynamic-system-prompt-sections"]
    elif body == "codex":
        ch = home / ".codex"
        files.append({"path": str(ch / "config.toml"), "content":
            f'model = "{model}"\nmodel_provider = "hsproxy"\nmodel_reasoning_effort = "{EFFORT or "medium"}"\n[model_providers.hsproxy]\nname = "study proxy"\n'
            f'base_url = "{proxy}/api/v1"\nenv_key = "OPENROUTER_API_KEY"\nwire_api = "responses"\n'})
        env = dict(base, CODEX_HOME=str(ch))
        argv = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "--json",
                "--output-last-message", str(work.parent / "final_message.txt"), "--", task]
    elif body == "opencode":
        cfg = home / ".config" / "opencode"
        files.append({"path": str(cfg / "opencode.json"), "content": json.dumps({
            "$schema": "https://opencode.ai/config.json",
            "provider": {"openrouter": {"options": {"baseURL": f"{proxy}/api/v1"}}},
            "small_model": f"openrouter/{model}"})})  # pin the side-call (session title) model too; audited in the proxy log
        env = dict(base, XDG_CONFIG_HOME=str(home / ".config"), XDG_DATA_HOME=str(home / ".local/share"),
                   XDG_STATE_HOME=str(home / ".local/state"))
        argv = ["opencode", "run", "--model", f"openrouter/{model}"] + (["--variant", EFFORT] if EFFORT else []) + [task]
    elif body == "pi":
        pa = home / ".pi" / "agent"
        files.append({"path": str(pa / "models.json"), "content": json.dumps({"providers": {"hsproxy": {
            "baseUrl": f"{proxy}/api/v1", "api": "openai-completions", "apiKey": "$OPENROUTER_API_KEY",
            "models": [{"id": model}]}}})})
        env = dict(base)
        argv = ["pi", "--provider", "hsproxy", "--model", model] + (["--thinking", EFFORT] if EFFORT else []) + ["-p", task]
    else:
        raise ValueError(f"unknown body {body!r}; bodies are {', '.join(BODIES)}")
    if write:
        for f in files:
            p = Path(f["path"]); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(f["content"])
        for d in (".claude", ".codex", ".config", ".local/share", ".local/state"):
            (home / d).mkdir(parents=True, exist_ok=True)
    return {"body": body, "native": False, "proxy": proxy, "model": model, "argv": argv, "env": env, "files": files}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="print the composition as JSON (the only output mode)")
    ap.add_argument("--body", required=True, choices=BODIES); ap.add_argument("--model", required=True)
    ap.add_argument("--home", required=True); ap.add_argument("--work", required=True)
    ap.add_argument("--proxy", default=None); ap.add_argument("--run-token", required=True)
    ap.add_argument("--task-file"); ap.add_argument("--task-placeholder", default="<task>")
    ap.add_argument("--max-turns", type=int, default=25); ap.add_argument("--agy-model", default=AGY_MODEL_DEFAULT)
    ap.add_argument("--effort", default=AGY_EFFORT_DEFAULT); ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    task = Path(a.task_file).read_text() if a.task_file else a.task_placeholder
    proxy = a.proxy if a.body != "antigravity" else None
    d = compose(a.body, a.model, Path(a.home), Path(a.work), proxy, a.run_token, task, max_turns=a.max_turns,
                agy_model=a.agy_model, effort=a.effort, write=a.write)
    json.dump(d, sys.stdout, indent=2); sys.stdout.write("\n")


if __name__ == "__main__":
    main()
