import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { describe, it } from "node:test";

import { main } from "../src/cli.ts";
import {
  agentOnPane,
  paneCwdFrom,
  paneIdFrom,
  paneInWorkDir,
  paneLabel,
  parsePrep,
  parseWatchArgs,
  placeholderArgv,
  renderPaneCommand,
  runWatch,
  shellQuote,
  stampStarted,
  type Prep,
  type PrepareRequest,
  type WatchDeps,
} from "../src/watch.ts";
import { capture, fixtureCompose, fixtureLaunches, REPO } from "./helpers.ts";

const TASK = resolve(REPO, "study", "tasks", "example-001");
const ALL = "antigravity,claude,codex,opencode,pi";

describe("renderPaneCommand", () => {
  it("reads the task from the prompt file and single-quotes everything else that needs it", () => {
    const cmd = renderPaneCommand(["agy", "-p", "<task>", "--model", "gemini-3.8-flash-medium"], "/tmp/hs-work/x/prompt.md");
    assert.equal(cmd, `agy -p "$(cat '/tmp/hs-work/x/prompt.md')" --model gemini-3.8-flash-medium`);
    const spicy = renderPaneCommand(["pi", "--x", "a $HOME 'q' b", "<task>"], "/tmp/my dir/prompt.md");
    assert.equal(spicy, `pi --x 'a $HOME '\\''q'\\'' b' "$(cat '/tmp/my dir/prompt.md')"`);
    assert.equal(shellQuote(""), "''");
    assert.equal(shellQuote("--flag=1"), "--flag=1");
  });

  it("tees stdout into <out_dir>/stdout.log so an Antigravity hand run keeps its stream-json record", () => {
    const cmd = renderPaneCommand(["agy", "-p", "<task>"], "/tmp/hs-work/x/prompt.md", "/tmp/o/run-1/stdout.log");
    assert.equal(cmd, `mkdir -p /tmp/o/run-1 && agy -p "$(cat '/tmp/hs-work/x/prompt.md')" | tee /tmp/o/run-1/stdout.log`);
    const spaced = renderPaneCommand(["pi", "<task>"], "/p/prompt.md", "/my out/r/stdout.log");
    assert.equal(spaced, `mkdir -p '/my out/r' && pi "$(cat '/p/prompt.md')" | tee '/my out/r/stdout.log'`);
  });
});

describe("parseWatchArgs", () => {
  it("takes one task dir, defaults, and validates state and level", () => {
    const args = parseWatchArgs([TASK, "--dry-run", "--bodies", "pi", "--state", "B", "--level", "2", "--out", "o"]);
    assert.equal(args.task, TASK);
    assert.deepEqual(args.bodies, ["pi"]);
    assert.equal(args.state, "B");
    assert.equal(args.level, "2");
    assert.equal(args.out, resolve("o"));
    assert.equal(parseWatchArgs([TASK]).out, resolve(REPO, "study", "samples", "hand-runs"));
    assert.equal(args.dryRun, true);
    assert.throws(() => parseWatchArgs([]), /TASK_DIR/);
    assert.throws(() => parseWatchArgs([TASK, "extra"]), /one TASK_DIR/);
    assert.throws(() => parseWatchArgs([TASK, "--level", "9"]), /--level/);
  });
});

describe("prep parsing and pane helpers", () => {
  it("parses the run.py --prepare-only JSON, last JSON line wins", () => {
    const text = `note\n${JSON.stringify({ prep_json: "/r/prep.json", run_id: "r1", work: "/w", home: "/h", wroot: "/r", prompt_file: "/r/prompt.md", argv: ["pi", "<task>"], env: { PATH: "/bin" }, native: false, out_dir: "/o/r1" })}\n`;
    const prep = parsePrep(text, "pi");
    assert.equal(prep.prep_json, "/r/prep.json");
    assert.equal(prep.out_dir, "/o/r1");
    assert.deepEqual(prep.argv, ["pi", "<task>"]);
    assert.throws(() => parsePrep("nope", "pi"), /no prep JSON/);
  });

  it("puts the placeholder back when prep argv carries the instruction text", () => {
    const text = "Implement f in solution.py.\nReport what you did.\n";
    assert.deepEqual(placeholderArgv(["pi", "-p", text.trim()], text), ["pi", "-p", "<task>"]);
    assert.deepEqual(placeholderArgv(["pi", "-p", "<task>"], text), ["pi", "-p", "<task>"]);
    assert.deepEqual(placeholderArgv(["pi", "-p", "other"], undefined), ["pi", "-p", "other"]);
  });

  it("finds the agent on a pane, the pane id from a create result, and the label", () => {
    assert.equal(agentOnPane([{ pane_id: "p1", name: "a1" }], "p1"), "a1");
    assert.equal(agentOnPane([{ pane_id: "p1" }], "p1"), "p1");
    assert.equal(agentOnPane([{ pane_id: "p2" }], "p1"), undefined);
    assert.equal(paneIdFrom({ result: { pane: { pane_id: "w1:p3" } } }), "w1:p3");
    assert.throws(() => paneIdFrom({ result: {} }), /pane_id/);
    assert.equal(paneLabel("pi", "example-001", "A", "1"), "pi · example-001 · A1");
  });

  it("tells a root pane that ignored --cwd from a fresh pane by the cwd the create result reports", () => {
    assert.equal(paneCwdFrom({ result: { pane: { pane_id: "w1:p1", cwd: "/Users/x" } } }), "/Users/x");
    assert.equal(paneCwdFrom({ result: { pane: { pane_id: "w1:p1" } } }), undefined);
    assert.equal(paneInWorkDir("/Users/x", "/tmp/hs-work/r/work"), false);
    assert.equal(paneInWorkDir(undefined, "/tmp/hs-work/r/work"), true);
    assert.equal(paneInWorkDir(REPO, resolve(REPO, "src", "..")), true);
  });

  it("stamps started into prep.json's manifest and leaves the rest alone", () => {
    const dir = mkdtempSync(resolve(tmpdir(), "mrh-stamp-"));
    const path = resolve(dir, "prep.json");
    writeFileSync(path, JSON.stringify({ run_id: "r", manifest: { started: null, ended: null, exit: null } }));
    stampStarted(path, 1_700_000_000_500);
    const rec = JSON.parse(readFileSync(path, "utf8")) as { run_id: string; manifest: Record<string, unknown> };
    assert.equal(rec.run_id, "r");
    assert.equal(rec.manifest.started, 1_700_000_000.5);
    assert.equal(rec.manifest.ended, null);
    rmSync(dir, { recursive: true, force: true });
  });
});

describe("mrh watch --dry-run", () => {
  it("prints one create, one run, one rename per body and touches nothing", async () => {
    const out = capture();
    const code = await main(["watch", TASK, "--dry-run", "--bodies", ALL, "--model", "google/gemini-3.8-flash"], {
      write: out.write,
      watch: { compose: fixtureCompose, env: { HS_WORK_ROOT: "/tmp/hs-work" } },
    });
    assert.equal(code, 0);
    const text = out.text();
    assert.equal((text.match(/pane create --crew --bind/g) ?? []).length, 5);
    assert.equal((text.match(/pane run /g) ?? []).length, 5);
    assert.equal((text.match(/"\$\(cat /g) ?? []).length, 5);
    assert.equal((text.match(/pane rename /g) ?? []).length, 5);
    assert.match(text, /^mrh-runtime pane create --crew --bind body0 --cwd \/tmp\/hs-work\/dry-antigravity\/work --env /m);
    assert.match(text, /--no-focus$/m);
    assert.match(text, /^mrh-runtime pane run <pane0> mkdir -p \S+\/dry-antigravity && agy -p "\$\(cat '\/tmp\/hs-work\/dry-antigravity\/prompt\.md'\)" --model gemini-3\.8-flash-medium .* \| tee \S+\/dry-antigravity\/stdout\.log$/m);
    assert.match(text, /pane rename <pane1> 'claude · example-001 · A1'/);
    assert.equal((text.match(/^prep: /gm) ?? []).length, 5);
    assert.match(text, /finish with: mrh run --finish/);
    assert.ok(!text.includes("sk-or-"));
  });
});

describe("mrh watch live (all spawns injected)", () => {
  it("refuses without the proxy or the server", async () => {
    const err = capture();
    const code = await runWatch([TASK, "--bodies", "pi"], {
      error: err.write,
      write: () => {},
      health: async () => ({ ok: false, detail: "ECONNREFUSED" }),
      serverRunning: () => true,
      env: {},
    });
    assert.equal(code, 1);
    assert.match(err.text(), /proxy .*ECONNREFUSED/);
    const err2 = capture();
    const code2 = await runWatch([TASK, "--bodies", "pi"], {
      error: err2.write,
      write: () => {},
      health: async () => ({ ok: true, detail: "200" }),
      serverRunning: () => false,
      env: {},
    });
    assert.equal(code2, 1);
    assert.match(err2.text(), /server not running/);
  });

  const fakePrep = (req: PrepareRequest): Prep => ({
    prep_json: `/tmp/o/${req.body}/prep.json`,
    run_id: `${req.body}-r`,
    work: `/tmp/hs-work/${req.body}/work`,
    home: `/tmp/hs-work/${req.body}/home`,
    wroot: `/tmp/hs-work/${req.body}`,
    prompt_file: `/tmp/hs-work/${req.body}/prompt.md`,
    out_dir: `/tmp/o/${req.body}-r`,
    argv: fixtureLaunches()[req.body].argv.map((e) => (e === "<task>" ? "Implement it.\nReport what you did.\n" : e)),
    env: { PATH: "/bin" },
    native: false,
  });

  /** Every spawn injected; `q` after three wall ticks. */
  function liveDeps(over: Partial<WatchDeps> = {}) {
    const calls: string[][] = [];
    const ran: [string, string][] = [];
    const killed: string[] = [];
    const paneKilled: string[] = [];
    const stamped: [string, number][] = [];
    const out = capture();
    const err = capture();
    let t = 1_000_000;
    let ticks = 0;
    let pressed: ((key: string) => void) | undefined;
    const deps: WatchDeps = {
      write: out.write,
      error: err.write,
      env: {},
      health: async () => ({ ok: true, detail: "200" }),
      serverRunning: () => true,
      prepare: fakePrep,
      readPrompt: (path) => (path.endsWith("/prompt.md") ? "Implement it.\nReport what you did.\n" : undefined),
      mux: (args) => {
        calls.push(args);
        if (args[1] === "create") return { result: { pane: { pane_id: `p-${args[4]}`, cwd: args[6] } } };
        return {};
      },
      paneRun: (paneId, cmd) => void ran.push([paneId, cmd]),
      listAgents: () => [
        { pane_id: "p-body0", name: "ag0", agent_status: "working" },
        { pane_id: "p-body1", name: "ag1", agent_status: "idle" },
        { pane_id: "p-other", name: "stranger", agent_status: "working" },
      ],
      readPane: (target) => `tail of ${target}`,
      kill: (name) => void killed.push(name),
      paneKill: (paneId) => void paneKilled.push(paneId),
      stamp: (prepJson, startedAt) => void stamped.push([prepJson, startedAt]),
      sleep: async () => {
        t += 1000;
        ticks += 1;
        if (ticks >= 3) pressed?.("q");
        await new Promise((r) => setImmediate(r));
      },
      keys: (onKey) => {
        pressed = onKey;
        return () => {
          pressed = undefined;
        };
      },
      now: () => t,
      agentWaitMs: 1000,
      ...over,
    };
    return { deps, calls, ran, killed, paneKilled, stamped, out, err };
  }

  it("prepares on the host, creates panes, runs the command with tee, stamps started, renames, draws the wall, stops on q", async () => {
    const { deps, calls, ran, killed, paneKilled, stamped, out } = liveDeps();
    const code = await runWatch([TASK, "--bodies", "pi,claude", "--out", "/tmp/o"], deps);
    assert.equal(code, 0);
    assert.deepEqual(calls[0], ["workspace", "list"]);
    assert.equal(calls.filter((c) => c[0] === "workspace" && c[1] === "create").length, 0);
    assert.deepEqual(calls[1]!.slice(0, 7), ["pane", "create", "--crew", "--bind", "body0", "--cwd", "/tmp/hs-work/pi/work"]);
    assert.ok(calls[1]!.includes("--no-focus"));
    assert.equal(calls.filter((c) => c[0] === "pane" && c[1] === "create").length, 2);
    assert.deepEqual(calls.filter((c) => c[1] === "rename").map((c) => c.slice(2)), [
      ["p-body0", "pi · example-001 · A1"],
      ["p-body1", "claude · example-001 · A1"],
    ]);
    assert.equal(ran.length, 2);
    assert.equal(ran[0]![0], "p-body0");
    assert.match(ran[0]![1], /^mkdir -p \/tmp\/o\/pi-r && pi --provider hsproxy --model google\/gemini-3\.8-flash -p "\$\(cat '\/tmp\/hs-work\/pi\/prompt\.md'\)" \| tee \/tmp\/o\/pi-r\/stdout\.log$/);
    assert.deepEqual(stamped.map(([p]) => p), ["/tmp/o/pi/prep.json", "/tmp/o/claude/prep.json"]);
    assert.ok(stamped.every(([, at]) => at >= 1_000_000));
    const text = out.text();
    assert.match(text, /prep: \/tmp\/o\/pi\/prep\.json/);
    assert.match(text, /mrh watch example-001/);
    assert.match(text, /tail of p-body0/);
    assert.ok(!text.includes("stranger"));
    assert.deepEqual(killed, ["ag0", "ag1"]);
    assert.deepEqual(paneKilled, []);
  });

  it("passes --sandbox host to run.py --prepare-only", async () => {
    const seen: PrepareRequest[] = [];
    const { deps } = liveDeps({ prepare: (req) => (seen.push(req), fakePrep(req)) });
    await runWatch([TASK, "--bodies", "pi", "--out", "/tmp/o"], deps);
    assert.equal(seen.length, 1);
    // the argv is built inside prepareHandRun; the request itself carries the absolute --out and the task
    assert.equal(seen[0]!.out, "/tmp/o");
    assert.equal(seen[0]!.task, TASK);
  });

  it("creates a workspace when the session has none, then the panes", async () => {
    let workspaces: unknown[] = [];
    const { deps, calls, ran } = liveDeps({
      mux: (args) => {
        calls.push(args);
        if (args[0] === "workspace" && args[1] === "list") return { result: { workspaces } };
        if (args[0] === "workspace" && args[1] === "create") {
          workspaces = [{ workspace_id: "w1" }];
          return { result: { workspace: { workspace_id: "w1" }, root_pane: { pane_id: "w1:p1", cwd: "/tmp/hs-work" } } };
        }
        if (args[1] === "create") return { result: { pane: { pane_id: `p-${args[4]}`, cwd: args[6] } } };
        return {};
      },
    });
    const code = await runWatch([TASK, "--bodies", "pi", "--out", "/tmp/o"], deps);
    assert.equal(code, 0);
    assert.deepEqual(calls.slice(0, 2), [
      ["workspace", "list"],
      ["workspace", "create", "--cwd", "/tmp/hs-work", "--label", "mrh watch example-001", "--no-focus"],
    ]);
    assert.equal(calls.filter((c) => c[0] === "workspace" && c[1] === "create").length, 1);
    assert.deepEqual(ran.map(([id]) => id), ["p-body0"]);
  });

  it("creates again when the first create hands back the workspace root pane (cwd not the work dir)", async () => {
    let creates = 0;
    const { deps, calls, ran } = liveDeps({
      mux: (args) => {
        calls.push(args);
        if (args[1] !== "create") return {};
        creates += 1;
        if (creates === 1) return { result: { pane: { pane_id: "w1:p1", cwd: "/Users/x" } } };
        return { result: { pane: { pane_id: `w1:p${creates + 1}`, cwd: args[6] } } };
      },
    });
    const code = await runWatch([TASK, "--bodies", "pi,claude", "--out", "/tmp/o"], deps);
    assert.equal(code, 0);
    assert.equal(creates, 3);
    assert.deepEqual(ran.map(([id]) => id), ["w1:p3", "w1:p4"]);
  });

  it("fails before launching anything when the multiplexer keeps ignoring --cwd, and names the prep dirs", async () => {
    const { deps, ran, out, err } = liveDeps({
      mux: (args) => (args[1] === "create" ? { result: { pane: { pane_id: "w1:p1", cwd: "/Users/x" } } } : {}),
    });
    const code = await main(["watch", TASK, "--bodies", "pi,claude", "--out", "/tmp/o"], { write: out.write, error: err.write, watch: deps });
    assert.equal(code, 1);
    assert.equal(ran.length, 0);
    assert.match(err.text(), /pane create returned w1:p1 in \/Users\/x, not the work dir \/tmp\/hs-work\/pi\/work/);
    assert.match(out.text(), /prepared, not launched: \/tmp\/o\/pi\/prep\.json\nprepared, not launched: \/tmp\/o\/claude\/prep\.json\n/);
  });

  it("prints each prep: line as soon as its pane runs, so a later failure leaves no launched run unnamed", async () => {
    let n = 0;
    const { deps, out, err } = liveDeps({
      paneRun: () => {
        n += 1;
        if (n === 2) throw new Error("mrh-runtime pane run p-body1: pane_not_found");
      },
    });
    const code = await main(["watch", TASK, "--bodies", "pi,claude", "--out", "/tmp/o"], { write: out.write, error: err.write, watch: deps });
    assert.equal(code, 1);
    assert.match(out.text(), /^prep: \/tmp\/o\/pi\/prep\.json\nprepared, not launched: \/tmp\/o\/claude\/prep\.json\n$/);
    assert.match(err.text(), /pane_not_found/);
  });

  it("stops a pane with no detected agent through the pane verb, not the agent verb", async () => {
    const { deps, killed, paneKilled } = liveDeps({ listAgents: () => [{ pane_id: "p-body1", name: "ag1", agent_status: "working" }] });
    const code = await runWatch([TASK, "--bodies", "pi,claude", "--out", "/tmp/o"], deps);
    assert.equal(code, 0);
    assert.deepEqual(killed, ["ag1"]);
    assert.deepEqual(paneKilled, ["p-body0"]);
  });
});
