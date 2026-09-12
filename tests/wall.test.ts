import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { formatScreen, formatWall } from "../src/mux/wall.ts";
import type { RosterRow } from "../src/mux/types.ts";

function row(partial: Partial<RosterRow> = {}): RosterRow {
  return {
    name: "pi",
    kind: "pi",
    status: "working",
    cwd: "/tmp",
    tabId: "w1:t1",
    paneId: "w1:p1",
    prompt: "example-001__pi__s0",
    lastLine: "Inspecting the layout",
    createdAt: new Date(Date.now() - 65_000).toISOString(),
    ...partial,
  };
}

describe("formatWall", () => {
  it("draws one box per pane with lane, elapsed and recent lines", () => {
    const text = formatWall([row(), row({ name: "codex", kind: "codex", status: "idle", paneId: "w1:p2", prompt: "", lastLine: "ready" })]);
    assert.match(text, /^mrh watch {2}2 panes {2}1 running · 1 idle · 0 inactive/);
    assert.match(text, /╭─ ● {2}pi {2}running {2}1m\d+s {2}w1:p1/);
    assert.match(text, /│ > example-001__pi__s0/);
    assert.match(text, /Inspecting the layout/);
    assert.match(text, /○ {2}codex {2}idle/);
    assert.match(text, /╰─/);
    assert.ok(!text.includes("herdr"));
    assert.ok(!text.includes("/wait"));
    assert.ok(!text.includes("admitted"));
  });

  it("shows up to three recent pane lines", () => {
    const lines = formatScreen(row({ lastLine: "noise\nread solution.py\nrunning pytest\n3 failed" }));
    const text = lines.join("\n");
    assert.match(text, /read solution.py/);
    assert.match(text, /running pytest/);
    assert.match(text, /3 failed/);
    assert.ok(!text.includes("noise"));
  });

  it("caps the wall and names the empty case", () => {
    const rows = Array.from({ length: 5 }, (_, i) => row({ name: `h${i}`, paneId: `p${i}`, status: i === 0 ? "working" : "done" }));
    assert.match(formatWall(rows, { maxScreens: 2 }), /\+ 3 more/);
    assert.match(formatWall([]), /no panes/);
    assert.match(formatWall([], { model: "google/gemini-3.8-flash" }), /google\/gemini-3\.8-flash/);
  });
});
