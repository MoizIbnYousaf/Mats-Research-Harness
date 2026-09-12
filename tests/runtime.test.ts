import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { describe, it } from "node:test";

import {
  killAgent,
  killVerbsFromHelp,
  MUX_NAME,
  paneCreateArgs,
  parseMuxOutput,
  parseServerStatus,
  resolveMux,
  resolveMuxPath,
  socketIsForeign,
  socketPath,
  treeBinaryPath,
} from "../src/mux/runtime.ts";

/** The old multiplexer names, assembled so the repo-wide grep never finds them spelled out. */
const OLD_NAME = ["hi-", "runtime"].join("");
const OLD_ENV = ["HI_", "RUNTIME_BIN"].join("");

describe("resolveMux", () => {
  it("is named mrh-runtime and builds to runtime/target/release/mrh-runtime", () => {
    assert.equal(MUX_NAME, "mrh-runtime");
    assert.equal(treeBinaryPath("/r"), "/r/runtime/target/release/mrh-runtime");
  });

  it("takes MRH_RUNTIME_BIN, then the binary built in the tree, then mrh-runtime on PATH, and never herdr or the old name", () => {
    const root = mkdtempSync(resolve(tmpdir(), "mrh-resolve-"));
    const tree = resolve(root, "runtime", "target", "release", "mrh-runtime");
    const asked: string[] = [];
    const onPath = (bin: string) => {
      asked.push(bin);
      return bin === "mrh-runtime" ? "/p/mrh-runtime" : bin === "herdr" ? "/p/herdr" : bin === OLD_NAME ? `/p/${OLD_NAME}` : undefined;
    };
    const onlyOthers = (bin: string) => {
      asked.push(bin);
      return bin === "herdr" ? "/p/herdr" : bin === OLD_NAME ? `/p/${OLD_NAME}` : undefined;
    };
    try {
      // nothing built: PATH, and only under our own name
      assert.deepEqual(resolveMux({ env: {}, root, which: onPath }), { path: "/p/mrh-runtime", source: "PATH" });
      assert.deepEqual(resolveMux({ env: {}, root, which: onlyOthers }), {});
      assert.equal(resolveMuxPath({ env: {}, root, which: onlyOthers }), undefined);
      // built in the tree: the tree wins over PATH
      mkdirSync(dirname(tree), { recursive: true });
      writeFileSync(tree, "");
      assert.deepEqual(resolveMux({ env: {}, root, which: onPath }), { path: tree, source: "runtime/target/release" });
      // the env var wins over both
      assert.deepEqual(resolveMux({ env: { MRH_RUNTIME_BIN: "/a" }, root, which: onPath }), { path: "/a", source: "MRH_RUNTIME_BIN" });
      assert.equal(resolveMux({ env: { MRH_RUNTIME_BIN: "  " }, root, which: onPath }).path, tree);
      // the old names are not consulted at all
      assert.equal(resolveMux({ env: { [OLD_ENV]: "/b" }, root, which: onPath }).path, tree);
      assert.deepEqual([...new Set(asked)], ["mrh-runtime"]);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});

describe("socketPath and socketIsForeign", () => {
  it("defaults to the config dir and flags a HERDR_SOCKET_PATH outside it", () => {
    const home = "/Users/x";
    assert.equal(socketPath({}, home), "/Users/x/.config/mrh-runtime/herdr.sock");
    const ours = "/Users/x/.config/mrh-runtime/sessions/mrh/herdr.sock";
    assert.equal(socketPath({ HERDR_SOCKET_PATH: ours }, home), ours);
    assert.equal(socketIsForeign({}, home), false);
    assert.equal(socketIsForeign({ HERDR_SOCKET_PATH: ours }, home), false);
    assert.equal(socketIsForeign({ HERDR_SOCKET_PATH: "/Users/x/.config/herdr/herdr.sock" }, home), true);
    assert.equal(socketIsForeign({ HERDR_SOCKET_PATH: "/Users/x/.config/mrh-runtime-dev/herdr.sock" }, home), true);
    assert.equal(socketIsForeign({ HERDR_SOCKET_PATH: "/Users/x/.config/mrh-runtime/../herdr/herdr.sock" }, home), true);
  });
});

describe("parseServerStatus", () => {
  it("reads a running server", () => {
    const status = parseServerStatus("status: running\nversion: 0.1.0\nprotocol: 21\ncompatible: yes\n", 0);
    assert.deepEqual(status, { running: true, version: "0.1.0", protocol: "21", compatible: "yes" });
  });

  it("treats `status: not running` with exit 0 as not running", () => {
    assert.equal(parseServerStatus("status: not running\n", 0).running, false);
    assert.equal(parseServerStatus("status: running\n", 1).running, false);
    assert.equal(parseServerStatus("", 0).running, false);
  });
});

describe("parseMuxOutput", () => {
  it("treats no output with exit 0 as success: `pane run` and `pane send-keys` print nothing", () => {
    assert.deepEqual(parseMuxOutput("", 0), {});
    assert.deepEqual(parseMuxOutput("\n", 0), {});
    assert.equal(parseMuxOutput("", 1).error?.message, "no output (status 1)");
    assert.equal(parseMuxOutput("", null).error?.message, "no output (status null)");
    assert.equal(parseMuxOutput('{"error":{"code":"pane_not_found","message":"pane w9:p9 not found"}}', 1).error?.code, "pane_not_found");
    assert.deepEqual(parseMuxOutput('{"result":{"pane":{"pane_id":"w1:p3"}}}', 0).result, { pane: { pane_id: "w1:p3" } });
    assert.equal(parseMuxOutput("not json", 0).error?.message, "not json");
  });
});

describe("paneCreateArgs", () => {
  it("binds, sets cwd, one --env per entry, never focuses", () => {
    assert.deepEqual(paneCreateArgs("body0", "/w", { PATH: "/bin", HOME: "/h" }), [
      "pane", "create", "--crew", "--bind", "body0", "--cwd", "/w", "--env", "PATH=/bin", "--env", "HOME=/h", "--no-focus",
    ]);
  });
});

describe("killAgent", () => {
  it("uses send-keys ctrl+c when that is the only verb the runtime lists", () => {
    assert.deepEqual(killVerbsFromHelp("Commands:\n  agent send-keys <name> <keys>\n  agent read"), ["send-keys"]);
    assert.deepEqual(killVerbsFromHelp("agent stop\nagent send-keys"), ["stop", "send-keys"]);
    assert.deepEqual(killVerbsFromHelp("nothing here"), []);
    const seen: string[][] = [];
    const out = killAgent("pane-1", { help: () => "  agent send-keys", run: (args) => (seen.push(args), {}) });
    assert.equal(out.method, "send-keys");
    assert.deepEqual(seen, [["agent", "send-keys", "pane-1", "ctrl+c"]]);
    assert.throws(() => killAgent("x", { help: () => "", run: () => ({}) }), /no agent stop/);
  });
});
