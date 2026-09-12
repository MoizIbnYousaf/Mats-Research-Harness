import assert from "node:assert/strict";
import { resolve } from "node:path";
import { describe, it } from "node:test";

import { formatDump, formatLaunchText, parseDumpArgs, readTaskHeader, runDump } from "../src/dump.ts";
import { isSecretEnvName } from "../src/env.ts";
import { main } from "../src/cli.ts";
import { capture, fixtureCompose, fixtureLaunches, REPO } from "./helpers.ts";

const TASK = resolve(REPO, "study", "tasks", "example-001");

describe("parseDumpArgs", () => {
  it("defaults to all five bodies and the pinned model; --task is required", () => {
    const args = parseDumpArgs(["--task", TASK]);
    assert.deepEqual(args.bodies, ["antigravity", "claude", "codex", "opencode", "pi"]);
    assert.equal(args.model, "deepseek/deepseek-v4-flash-0731");
    assert.equal(args.json, false);
    assert.throws(() => parseDumpArgs([]), /--task/);
    // the launch lines do not depend on state or level, so dump takes neither
    assert.throws(() => parseDumpArgs(["--task", TASK, "--state", "B"]), /unknown dump flag: --state/);
    assert.throws(() => parseDumpArgs(["--task", TASK, "--level", "2"]), /unknown dump flag: --level/);
    assert.deepEqual(parseDumpArgs(["--task", TASK, "--bodies", "pi,claude", "--json"]).bodies, ["pi", "claude"]);
  });

  it("reads the task id from task.toml", () => {
    assert.equal(readTaskHeader(TASK).id, "example-001");
  });
});

describe("formatLaunchText", () => {
  it("prints the exact block for a proxied body with secret-shaped names as set|unset", () => {
    const launch = { ...fixtureLaunches().claude, env: { ...fixtureLaunches().claude.env, FAKE_API_KEY: "sk-or-abc" } };
    const lines = formatLaunchText(launch, isSecretEnvName);
    assert.equal(lines[0], "== claude (proxied)");
    assert.equal(lines[1], "cwd: /tmp/hs-work/dry/work");
    assert.equal(lines[2], "proxy: http://127.0.0.1:8931");
    assert.equal(lines[3], "model: google/gemini-3.8-flash");
    assert.equal(lines[4], "argv: claude --model google/gemini-3.8-flash -p <task> --output-format stream-json --verbose --dangerously-skip-permissions --max-turns 25");
    assert.equal(lines[5], "env:");
    const env = lines.slice(6, lines.indexOf("files:"));
    assert.deepEqual(env, [...env].sort());
    assert.ok(env.includes("  ANTHROPIC_BASE_URL=http://127.0.0.1:8931/api"));
    assert.ok(env.includes("  ANTHROPIC_AUTH_TOKEN=set (run token, not the key)"));
    assert.ok(env.includes("  OPENROUTER_API_KEY=set (run token, not the key)"));
    assert.ok(env.includes("  ANTHROPIC_API_KEY=unset"));
    assert.ok(env.includes("  FAKE_API_KEY=set"));
    assert.ok(!lines.join("\n").includes("sk-or-"));
    assert.ok(!lines.join("\n").includes("hs_dry"));
  });

  it("prints the native block for antigravity with effort and no proxy", () => {
    const lines = formatLaunchText(fixtureLaunches().antigravity, isSecretEnvName);
    assert.equal(lines[0], "== antigravity (native)");
    assert.equal(lines[2], "proxy: none (native, account quota)");
    assert.equal(lines[3], "model: gemini-3.8-flash-medium (effort medium)");
    assert.equal(lines[4], "argv: agy -p <task> --model gemini-3.8-flash-medium --effort medium --output-format stream-json --dangerously-skip-permissions --print-timeout 10m");
    assert.equal(lines[lines.length - 1], "files:");
  });

  it("lists config files with byte counts", () => {
    const lines = formatLaunchText(fixtureLaunches().codex, isSecretEnvName);
    const files = lines.slice(lines.indexOf("files:") + 1);
    assert.equal(files.length, 1);
    assert.match(files[0]!, /^ {2}\/tmp\/hs-work\/dry\/home\/\.codex\/config\.toml \(\d+ bytes\)$/);
  });
});

describe("mrh dump", () => {
  it("prints five blocks separated by blank lines through the injected composer", async () => {
    const out = capture();
    const code = await main(["dump", "--task", TASK, "--model", "google/gemini-3.8-flash"], {
      write: out.write,
      dump: { compose: fixtureCompose, env: { HS_WORK_ROOT: "/tmp/hs-work" } },
    });
    assert.equal(code, 0);
    const text = out.text();
    assert.equal((text.match(/^== /gm) ?? []).length, 5);
    assert.equal((text.match(/^proxy: http:\/\/127\.0\.0\.1:8931$/gm) ?? []).length, 4);
    assert.equal((text.match(/^proxy: none \(native, account quota\)$/gm) ?? []).length, 1);
    assert.equal((text.match(/--dangerously-skip-permissions|--dangerously-bypass-approvals-and-sandbox/g) ?? []).length, 3);
    assert.equal((text.match(/OPENROUTER_API_KEY=set \(run token, not the key\)/g) ?? []).length, 4);
    assert.equal((text.match(/sk-or-/gi) ?? []).length, 0);
    assert.match(text, /^task: example-001( {2}entry_point \S+)?\n/);
    assert.equal(formatDump({ id: "t" }, [], isSecretEnvName), "task: t");
    assert.equal(formatDump({ id: "t", entryPoint: "f" }, [], isSecretEnvName), "task: t  entry_point f");
  });

  it("--json prints the redacted Launch array", () => {
    const out = capture();
    const code = runDump(["--task", TASK, "--bodies", "pi", "--json"], { compose: fixtureCompose, write: out.write, env: {} });
    assert.equal(code, 0);
    const parsed = JSON.parse(out.text()) as { body: string; env: Record<string, string> }[];
    assert.equal(parsed.length, 1);
    assert.equal(parsed[0]!.body, "pi");
    assert.equal(parsed[0]!.env.OPENROUTER_API_KEY, "set (run token, not the key)");
  });
});
