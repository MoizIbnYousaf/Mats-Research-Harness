import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { lastLineFromPane, recentPaneLines, rosterLastLine, textFromRead } from "../src/mux/events.ts";

describe("lastLineFromPane", () => {
  it("takes the last visible pane line", () => {
    assert.equal(lastLineFromPane("one\n  two  \n\nthree  ready"), "three ready");
  });
});

describe("recentPaneLines", () => {
  it("returns up to three recent non-empty pane or event lines", () => {
    assert.deepEqual(recentPaneLines("one\ntwo\nthree\nfour"), ["two", "three", "four"]);
    assert.deepEqual(recentPaneLines('a\n\n  b  \n{"event":"stop","response":"ok"}\n'), ["a", "b", "done · ok"]);
    assert.deepEqual(recentPaneLines("x\ny", 1), ["y"]);
  });
});

describe("textFromRead", () => {
  it("reads raw text or socket JSON", () => {
    assert.equal(textFromRead("raw"), "raw");
    assert.equal(textFromRead({ result: { read: { text: "one\n  last visible  " } } }), "one\n  last visible  ");
    assert.equal(textFromRead({ result: { text: "t" } }), "t");
    assert.equal(textFromRead(42), "");
  });
});

describe("rosterLastLine", () => {
  it("prefers an event, else the pane tail, else a verb for the status", () => {
    assert.equal(rosterLastLine({ lastLine: "tool done\nlast visible", prompt: "x", status: "working" }), "last visible");
    assert.equal(rosterLastLine({ lastLine: "", prompt: "run-1", status: "working" }), "running · run-1");
    assert.equal(rosterLastLine({ lastLine: "", prompt: "run-1", status: "done" }), "done · run-1");
    assert.equal(rosterLastLine({ lastLine: "", prompt: "", status: "idle" }), "needs input");
    assert.equal(rosterLastLine({ lastLine: '{"event":"idle_prompt"}', prompt: "x", status: "working" }), "needs input");
  });
});
