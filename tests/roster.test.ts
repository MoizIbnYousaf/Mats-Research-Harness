import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { countLanes, elapsedLabel, filterRoster, statusLane } from "../src/mux/compare.ts";
import { rosterLastLine } from "../src/mux/events.ts";
import { attachLastLines, buildRoster, collectLastLineReads } from "../src/mux/roster.ts";
import { hydrateRosterTails, loadLiveRoster } from "../src/mux/snapshot.ts";
import type { LaunchRecord } from "../src/mux/types.ts";

const launch: LaunchRecord = { run_id: "example-001__pi__s0", body: "pi", pane_id: "w1:p1", prep_json: "/r/prep.json", createdAt: "2026-09-02T00:00:00.000Z" };

describe("buildRoster", () => {
  it("merges the agent list with launched panes and keeps strangers under their own names", () => {
    const rows = buildRoster(
      [
        { pane_id: "w1:p1", agent: "pi", agent_status: "working", cwd: "/w" },
        { pane_id: "w1:p9", name: "other", agent: "codex", agent_status: "idle" },
      ],
      [launch],
    );
    assert.equal(rows.length, 2);
    assert.equal(rows[0]!.name, "pi");
    assert.equal(rows[0]!.kind, "pi");
    assert.equal(rows[0]!.prompt, "example-001__pi__s0");
    assert.equal(rows[0]!.createdAt, launch.createdAt);
    assert.equal(statusLane(rows[0]!.status), "running");
    assert.equal(rows[1]!.name, "other");
    assert.equal(rows[1]!.kind, "codex");
  });

  it("keeps a launched pane the agent list has not reported yet", () => {
    const rows = buildRoster([], [launch]);
    assert.equal(rows.length, 1);
    assert.equal(rows[0]!.status, "unknown");
    assert.equal(rows[0]!.paneId, "w1:p1");
  });

  it("keeps a last_line / event hint from the agent list", () => {
    const rows = buildRoster([{ pane_id: "w1:p1", agent: "pi", agent_status: "done", event: "stop", response: "ready" }], [launch]);
    assert.equal(rosterLastLine(rows[0]!), "done · ready");
  });
});

describe("attachLastLines", () => {
  it("overlays injected pane text keyed by pane id", () => {
    const rows = buildRoster([{ pane_id: "w1:p1", agent: "pi", agent_status: "working" }], [launch]);
    const reads = collectLastLineReads(rows, (target) => {
      assert.equal(target, "w1:p1");
      return "scroll\nlast visible from pane";
    });
    const decorated = attachLastLines(rows, reads);
    assert.equal(rosterLastLine(decorated[0]!), "last visible from pane");
  });

  it("reads running panes first and honors the limit", () => {
    const rows = buildRoster(
      [
        { pane_id: "p-idle", name: "idle-1", agent: "codex", agent_status: "idle" },
        { pane_id: "p-run", name: "run-1", agent: "pi", agent_status: "working" },
        { pane_id: "p-done", name: "done-1", agent: "pi", agent_status: "done" },
      ],
      [],
    );
    const seen: string[] = [];
    collectLastLineReads(rows, (target) => (seen.push(target), "line"), 1);
    assert.deepEqual(seen, ["p-run"]);
  });
});

describe("loadLiveRoster and filters", () => {
  it("attaches last-line from the injected read without calling the multiplexer", () => {
    const rows = loadLiveRoster({
      agents: [{ pane_id: "w1:p1", agent: "pi", agent_status: "done" }],
      launches: [launch],
      read: () => '{"event":"stop","response":"ready"}',
    });
    assert.equal(rows.length, 1);
    assert.equal(rosterLastLine(rows[0]!), "done · ready");
  });

  it("filters to the launched pane ids and hydrates only those", () => {
    const rows = loadLiveRoster({
      agents: [
        { pane_id: "p-x", name: "fleet", agent: "codex", agent_status: "working" },
        { pane_id: "w1:p1", agent: "pi", agent_status: "working" },
      ],
      launches: [launch],
      readLimit: 0,
    });
    const filtered = filterRoster(rows, { paneIds: ["w1:p1"] });
    const seen: string[] = [];
    const decorated = hydrateRosterTails(filtered, { readLimit: 2, read: (t) => (seen.push(t), "read solution.py\nall green") });
    assert.deepEqual(seen, ["w1:p1"]);
    assert.match(decorated[0]!.lastLine, /all green/);
    assert.deepEqual(countLanes(rows), { running: 2, idle: 0, inactive: 0 });
    assert.deepEqual(filterRoster(rows, { running: true, kind: "pi" }).map((r) => r.paneId), ["w1:p1"]);
  });

  it("labels elapsed time", () => {
    const start = Date.parse("2026-09-02T00:00:00.000Z");
    assert.equal(elapsedLabel("2026-09-02T00:00:00.000Z", start + 5_000), "5s");
    assert.equal(elapsedLabel("2026-09-02T00:00:00.000Z", start + 125_000), "2m5s");
    assert.equal(elapsedLabel("2026-09-02T00:00:00.000Z", start + 3_700_000), "1h1m");
    assert.equal(elapsedLabel(null), "");
  });
});
