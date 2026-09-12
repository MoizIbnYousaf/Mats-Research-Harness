import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { describe, it } from "node:test";

import { BODIES, composeArgs, composeLaunch, envMarker, parseBodies, parseLaunch, redactLaunch } from "../src/bodies.ts";
import { isSecretEnvName } from "../src/env.ts";
import { fixtureLaunches, REPO } from "./helpers.ts";

const opts = {
  model: "google/gemini-3.8-flash",
  home: "/tmp/hs-work/dry/home",
  work: "/tmp/hs-work/dry/work",
  proxy: "http://127.0.0.1:8931",
  runToken: "hs_dry",
} as const;

describe("composeLaunch", () => {
  it("parses the JSON harness_env.py --json prints and never passes --write", () => {
    const fixture = fixtureLaunches();
    const seen: string[][] = [];
    const launch = composeLaunch({
      ...opts,
      body: "claude",
      python: "python-fake",
      root: REPO,
      spawn: (cmd, args) => {
        assert.equal(cmd, "python-fake");
        seen.push(args);
        return { status: 0, stdout: JSON.stringify(fixture.claude), stderr: "" };
      },
    });
    assert.equal(launch.body, "claude");
    assert.equal(launch.native, false);
    assert.equal(launch.proxy, "http://127.0.0.1:8931");
    assert.deepEqual(launch.argv.slice(0, 3), ["claude", "--model", "google/gemini-3.8-flash"]);
    assert.equal(launch.env.ANTHROPIC_BASE_URL, "http://127.0.0.1:8931/api");
    const args = seen[0]!;
    assert.equal(args[0], resolve(REPO, "study", "runner", "harness_env.py"));
    assert.ok(args.includes("--json"));
    assert.ok(!args.includes("--write"));
    assert.deepEqual(args.slice(args.indexOf("--body"), args.indexOf("--body") + 2), ["--body", "claude"]);
    assert.deepEqual(args.slice(args.indexOf("--run-token"), args.indexOf("--run-token") + 2), ["--run-token", "hs_dry"]);
    assert.deepEqual(args.slice(args.indexOf("--task-placeholder"), args.indexOf("--task-placeholder") + 2), ["--task-placeholder", "<task>"]);
    assert.deepEqual(args.slice(args.indexOf("--work"), args.indexOf("--work") + 2), ["--work", "/tmp/hs-work/dry/work"]);
    assert.deepEqual(args.slice(args.indexOf("--home"), args.indexOf("--home") + 2), ["--home", "/tmp/hs-work/dry/home"]);
    assert.deepEqual(args.slice(args.indexOf("--proxy"), args.indexOf("--proxy") + 2), ["--proxy", "http://127.0.0.1:8931"]);
  });

  it("composeArgs carries only the documented flags", () => {
    const args = composeArgs({ ...opts, body: "pi" }, REPO);
    const flags = args.filter((a) => a.startsWith("--"));
    assert.deepEqual(flags, ["--json", "--body", "--model", "--home", "--work", "--proxy", "--run-token", "--task-placeholder"]);
  });

  it("fails loudly when the composer exits non-zero or prints no JSON", () => {
    assert.throws(
      () => composeLaunch({ ...opts, body: "pi", python: "x", root: REPO, spawn: () => ({ status: 2, stdout: "", stderr: "usage: harness_env.py" }) }),
      /harness_env\.py --json failed for pi/,
    );
    assert.throws(() => parseLaunch("not json", { body: "pi", model: opts.model, work: opts.work }), /no JSON/);
  });

  it("no env value in any fixture launch starts with sk-or-, and the token is named as such", () => {
    for (const launch of Object.values(fixtureLaunches())) {
      for (const value of Object.values(launch.env)) assert.ok(!value.startsWith("sk-or-"), `${launch.body} leaks a key`);
      for (const file of launch.files) assert.ok(!file.content.includes("sk-or-"), `${launch.body} file leaks a key`);
    }
    assert.equal(envMarker("hs_abc"), "set (run token, not the key)");
    assert.equal(envMarker("sk-or-abc"), "set");
    assert.equal(envMarker(""), "unset");
    const redacted = redactLaunch({ ...fixtureLaunches().pi, env: { OPENROUTER_API_KEY: "sk-or-abc", PATH: "/bin" } }, isSecretEnvName);
    assert.equal(redacted.env.OPENROUTER_API_KEY, "set");
    assert.equal(redacted.env.PATH, "/bin");
  });

  it("parses --bodies", () => {
    assert.deepEqual(parseBodies(undefined), [...BODIES]);
    assert.deepEqual(parseBodies("pi,claude,pi"), ["pi", "claude"]);
    assert.throws(() => parseBodies("grok"), /unknown body grok/);
  });
});

describe("harness_env.py --json (live, skipped without python3 and the --json flag)", () => {
  const script = resolve(REPO, "study", "runner", "harness_env.py");
  const python = spawnSync("python3", ["--version"], { encoding: "utf8" });
  const hasJsonFlag = existsSync(script) && spawnSync("grep", ["-q", "--", "--run-token", script]).status === 0;
  const skip = python.error || python.status !== 0 || !hasJsonFlag;

  it("meets the argv contract for all five bodies", { skip: skip ? "python3 or harness_env.py --json unavailable" : false }, () => {
    for (const body of BODIES) {
      const launch = composeLaunch({ ...opts, body, python: "python3", root: REPO });
      assert.equal(launch.body, body);
      for (const value of Object.values(launch.env)) assert.ok(!value.startsWith("sk-or-"));
      for (const file of launch.files) assert.ok(!file.content.includes("sk-or-"));
      const argv = launch.argv;
      if (body === "antigravity") {
        assert.equal(launch.native, true);
        assert.equal(launch.proxy, null);
        assert.deepEqual(argv, ["agy", "-p", "<task>", "--model", "gemini-3.8-flash-medium", "--effort", "medium", "--output-format", "stream-json", "--dangerously-skip-permissions", "--print-timeout", "10m"]);
        continue;
      }
      assert.equal(launch.native, false);
      assert.equal(launch.proxy, opts.proxy);
      if (body === "claude") {
        assert.deepEqual(argv, ["claude", "--model", opts.model, "-p", "<task>", "--output-format", "stream-json", "--verbose", "--dangerously-skip-permissions", "--max-turns", "25"]);
        assert.equal(launch.env.ANTHROPIC_BASE_URL, `${opts.proxy}/api`);
        assert.equal(launch.env.ANTHROPIC_AUTH_TOKEN, opts.runToken);
        assert.equal(launch.env.OPENROUTER_API_KEY, opts.runToken);
        assert.equal(launch.env.ANTHROPIC_MODEL, opts.model);
        assert.ok("CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT" in launch.env);
        assert.ok("CLAUDE_CONFIG_DIR" in launch.env);
      }
      if (body === "codex") {
        assert.deepEqual(argv.slice(0, 5), ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "--json", "--output-last-message"]);
        assert.match(argv[5]!, /final_message\.txt$/);
        assert.deepEqual(argv.slice(6), ["--", "<task>"]);
        assert.ok("CODEX_HOME" in launch.env);
        assert.equal(launch.env.OPENROUTER_API_KEY, opts.runToken);
        assert.ok(launch.files.some((f) => f.path.endsWith("config.toml")));
      }
      if (body === "opencode") {
        assert.deepEqual(argv, ["opencode", "run", "--model", `openrouter/${opts.model}`, "<task>"]);
        assert.ok(Object.keys(launch.env).some((k) => k.startsWith("XDG_")));
        assert.ok(launch.files.some((f) => f.path.endsWith("opencode.json")));
      }
      if (body === "pi") {
        assert.deepEqual(argv, ["pi", "--provider", "hsproxy", "--model", opts.model, "-p", "<task>"]);
        assert.ok(launch.files.some((f) => f.path.endsWith("models.json")));
      }
    }
  });
});
