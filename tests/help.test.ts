import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { main } from "../src/cli.ts";
import { usage, VERBS } from "../src/help.ts";
import { capture } from "./helpers.ts";

/** Product wording that must not appear; assembled from fragments so this file never spells it out. */
const FORBIDDEN = [
  ["harness", " ", "index"],
  ["harness", "index"],
  ["leader", "board"],
  ["saf", "est h"],
  ["best ", "harness"],
  ["which harness ", "is"],
].map((parts) => new RegExp(parts.join(""), "i"));

describe("usage", () => {
  it("lists every verb with its PLAN line and no product wording", () => {
    const text = usage();
    for (const verb of VERBS) assert.match(text, new RegExp(`^ {2}${verb}\\b`, "m"), `missing verb ${verb}`);
    for (const line of ["39", "26 and 33", "35 and 75", "line 35", "57-68", "line 31", "line 30", "line 78", "76-77"]) {
      assert.ok(text.includes(line), `missing PLAN line ${line}`);
    }
    for (const pattern of FORBIDDEN) assert.doesNotMatch(text, pattern);
    assert.deepEqual([...VERBS], ["doctor", "dump", "watch", "run", "batch", "score", "perceive", "verify", "figures"]);
  });
});

describe("main", () => {
  it("prints usage for help and exits 2 on an unknown verb or no verb", async () => {
    const out = capture();
    assert.equal(await main(["help"], { write: out.write }), 0);
    assert.match(out.text(), /Usage: mrh <verb>/);
    const err = capture();
    assert.equal(await main(["eval"], { write: () => {}, error: err.write }), 2);
    assert.match(err.text(), /unknown verb eval/);
    assert.equal(await main([], { write: () => {}, error: () => {} }), 2);
    assert.equal(await main(["--help"], { write: () => {} }), 0);
  });

  it("passes the study verbs through with their script and exit code", async () => {
    const seen: [string, string[]][] = [];
    const study = (script: string, args: string[]) => (seen.push([script, args]), 7);
    assert.equal(await main(["score", "--one", "/r"], { study }), 7);
    assert.equal(await main(["run", "--task", "t"], { study }), 7);
    assert.equal(await main(["batch", "--dry-run"], { study }), 7);
    assert.equal(await main(["perceive", "--runs", "d"], { study }), 7);
    assert.equal(await main(["verify", "--runs", "d"], { study }), 7);
    assert.equal(await main(["figures", "--runs", "d"], { study }), 7);
    assert.deepEqual(seen.map(([s]) => s), ["scoring/score.py", "runner/run.py", "runner/batch.py", "runner/perceive.py", "verify.py", "figures.py"]);
    assert.deepEqual(seen[0]![1], ["--one", "/r"]);
  });
});
