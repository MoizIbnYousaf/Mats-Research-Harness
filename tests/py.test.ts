import assert from "node:assert/strict";
import { resolve } from "node:path";
import { describe, it } from "node:test";

import { appRoot, resolvePython, runStudy } from "../src/py.ts";
import { REPO } from "./helpers.ts";

describe("resolvePython", () => {
  it("prefers MRH_PYTHON, then the study venv when executable, then python3", () => {
    const venv = resolve(REPO, "study", ".venv", "bin", "python");
    assert.equal(resolvePython({ MRH_PYTHON: "/opt/py" }, { root: REPO, executable: () => true }), "/opt/py");
    assert.equal(resolvePython({}, { root: REPO, executable: (p) => p === venv }), venv);
    assert.equal(resolvePython({}, { root: REPO, executable: () => false }), "python3");
    assert.equal(resolvePython({ MRH_PYTHON: "  " }, { root: REPO, executable: () => false }), "python3");
  });

  it("appRoot is the repository root", () => {
    assert.equal(appRoot(), REPO);
  });
});

describe("runStudy", () => {
  it("spawns <python> study/<script> ARGS from the caller's cwd, not the repo root, and returns the exit code", () => {
    const seen: { cmd: string; args: string[]; cwd: string }[] = [];
    const spawn = (cmd: string, args: string[], opts: { cwd: string }) => (seen.push({ cmd, args, cwd: opts.cwd }), 3);
    const code = runStudy("scoring/score.py", ["--one", "/r"], { root: REPO, python: "py-fake", env: {}, spawn });
    assert.equal(code, 3);
    assert.deepEqual(seen, [
      { cmd: "py-fake", args: [resolve(REPO, "study", "scoring", "score.py"), "--one", "/r"], cwd: process.cwd() },
    ]);
    runStudy("scoring/score.py", ["."], { root: REPO, python: "py-fake", env: {}, spawn, cwd: "/tmp/elsewhere" });
    assert.equal(seen[1]!.cwd, "/tmp/elsewhere");
  });
});
