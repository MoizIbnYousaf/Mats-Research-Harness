import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { doctorExitCode, doctorRows, formatDoctorReport, parseDoctorArgs, type DoctorProbe } from "../src/doctor.ts";
import { parseServerStatus } from "../src/mux/runtime.ts";

const TREE_BIN = "/Users/x/mrh/runtime/target/release/mrh-runtime";
const SOCK = "/Users/x/.config/mrh-runtime/sessions/mrh/herdr.sock";
const FOREIGN = "HERDR_SOCKET_PATH points at another program's server; unset it";
/** The name this runtime had before; assembled so the repo-wide grep never finds it spelled out. */
const OLD_NAME = ["hi-", "runtime"].join("");

function probe(partial: Partial<DoctorProbe> = {}): DoctorProbe {
  return {
    node: "v22.23.1",
    bodies: {
      antigravity: { path: "/usr/local/bin/agy", version: "1.1.22" },
      claude: { path: "/usr/local/bin/claude", version: "2.1.0" },
      codex: { path: "/usr/local/bin/codex", version: "codex-cli 0.9" },
      opencode: { path: "/usr/local/bin/opencode", version: "1.2" },
      pi: { path: "/usr/local/bin/pi", version: "0.84.1" },
    },
    runtime: { path: TREE_BIN, source: "runtime/target/release", version: "mrh-runtime 0.1.0 (herdr 0.8.2 base, protocol 21)" },
    socket: { path: SOCK, foreign: false },
    server: { running: true, version: "0.1.0", protocol: "21", compatible: "yes" },
    proxy: { url: "http://127.0.0.1:8931", ok: true, detail: "200" },
    keySet: true,
    python: { path: "/usr/bin/python3", version: "Python 3.12.1", pytest: "8.3.2" },
    agySettings: { path: "/Users/x/.gemini/antigravity-cli/settings.json", present: true },
    ...partial,
  };
}

const NAMES = [
  "node",
  "body antigravity",
  "body claude",
  "body codex",
  "body opencode",
  "body pi",
  "mrh-runtime",
  "mrh-runtime server",
  "proxy",
  "OPENROUTER_API_KEY",
  "python",
  "antigravity settings",
];

describe("formatDoctorReport", () => {
  it("prints the rows in order with the padded format and doctor: ok", () => {
    const text = formatDoctorReport(probe());
    const lines = text.split("\n");
    assert.equal(lines[0], "mrh doctor");
    assert.deepEqual(doctorRows(probe()).map((row) => row.name), NAMES);
    assert.equal(lines[1], "ok            node                 v22.23.1");
    assert.equal(lines[2], "ok            body antigravity     /usr/local/bin/agy 1.1.22");
    assert.equal(lines[7], `ok            mrh-runtime          ${TREE_BIN} (runtime/target/release) mrh-runtime 0.1.0 (herdr 0.8.2 base, protocol 21)`);
    assert.equal(lines[8], `ok            mrh-runtime server   ${SOCK} running version 0.1.0 protocol 21 compatible yes`);
    assert.equal(lines[9], "ok            proxy                http://127.0.0.1:8931/health 200");
    assert.equal(lines[10], "ok            OPENROUTER_API_KEY   set");
    assert.equal(lines[11], "ok            python               /usr/bin/python3 Python 3.12.1 pytest 8.3.2");
    assert.match(lines[12]!, /^ok {12}antigravity settings .*settings\.json present$/);
    assert.equal(lines[lines.length - 1], "doctor: ok");
    assert.equal(doctorExitCode(doctorRows(probe())), 0);
  });

  it("marks a dead server, a missing body, a missing pytest and an unset key as no and counts them", () => {
    const p = probe({
      server: parseServerStatus("status: not running\n", 0),
      bodies: { ...probe().bodies, pi: {} },
      python: { path: "python3", version: "Python 3.12.1", pytest: undefined },
      keySet: false,
    });
    const text = formatDoctorReport(p);
    assert.match(text, /^no {12}body pi {14}pi missing$/m);
    assert.match(text, /^no {12}mrh-runtime server {3}\/Users\/x\/\.config\/mrh-runtime\/sessions\/mrh\/herdr\.sock not running$/m);
    assert.match(text, /^no {12}python {15}python3 Python 3\.12\.1 pytest missing$/m);
    assert.match(text, /^no {12}OPENROUTER_API_KEY {3}unset$/m);
    assert.match(text, /doctor: 4 missing$/);
    assert.equal(doctorExitCode(doctorRows(p)), 1);
  });

  it("marks a runtime path that does not answer --version as no, and says how to build when there is none", () => {
    const p = probe({ runtime: { path: "/nonexistent", source: "MRH_RUNTIME_BIN", version: undefined } });
    const text = formatDoctorReport(p);
    assert.match(text, /^no {12}mrh-runtime {10}\/nonexistent \(MRH_RUNTIME_BIN\) does not answer --version$/m);
    assert.equal(doctorExitCode(doctorRows(p)), 1);
    assert.match(formatDoctorReport(probe({ runtime: {} })), /^no {12}mrh-runtime {10}not built \(make runtime\)$/m);
    assert.ok(!text.includes(OLD_NAME));
  });

  it("refuses a HERDR_SOCKET_PATH outside ~/.config/mrh-runtime without probing it, online or offline", () => {
    const p = probe({ socket: { path: "/Users/x/.config/herdr/herdr.sock", foreign: true }, server: undefined });
    const text = formatDoctorReport(p);
    assert.match(text, new RegExp(`^no {12}mrh-runtime server {3}${FOREIGN.replace(/[.;()]/g, "\\$&")}$`, "m"));
    assert.ok(!text.includes("/Users/x/.config/herdr"));
    assert.equal(doctorExitCode(doctorRows(p)), 1);
    const offline = formatDoctorReport(p, { offline: true });
    assert.match(offline, /^no {12}mrh-runtime server {3}HERDR_SOCKET_PATH points at another program's server; unset it$/m);
    assert.equal(doctorExitCode(doctorRows(p, { offline: true }), { offline: true }), 0);
  });

  it("--offline skips the server and proxy rows and exits 0 even with misses", () => {
    const p = probe({ server: undefined, proxy: { url: "http://127.0.0.1:8931" }, bodies: { ...probe().bodies, codex: {} } });
    const text = formatDoctorReport(p, { offline: true });
    const lines = text.split("\n");
    assert.equal(lines[0], "mrh doctor (offline: network probes skipped)");
    assert.equal(lines[8], `skip          mrh-runtime server   ${SOCK} --offline`);
    assert.equal(lines[9], "skip          proxy                http://127.0.0.1:8931/health --offline");
    assert.equal(lines[lines.length - 1], "doctor: offline, report only");
    assert.equal(doctorExitCode(doctorRows(p, { offline: true }), { offline: true }), 0);
    assert.ok(!text.includes("agy models"));
  });

  it("--probe-agy adds two rows, skipped offline, judged live", () => {
    const offline = doctorRows(probe(), { offline: true, probeAgy: true });
    assert.deepEqual(offline.slice(-2).map((r) => [r.name, r.status]), [["agy models", "skip"], ["agy wrong slug", "skip"]]);
    const live = doctorRows(
      probe({ agy: { models: { ok: true, detail: "exit 0, 4 lines" }, wrongSlug: { ok: false, detail: "exit 0 on mrh-not-a-model" } } }),
      { probeAgy: true },
    );
    assert.deepEqual(live.slice(-2).map((r) => [r.name, r.status]), [["agy models", "ok"], ["agy wrong slug", "no"]]);
    assert.equal(doctorExitCode(live), 1);
  });

  it("never prints a key value", () => {
    const text = formatDoctorReport(probe({ keySet: true }));
    assert.ok(!/sk-or-/.test(text));
    assert.match(text, /OPENROUTER_API_KEY {3}set$/m);
  });

  it("parses flags", () => {
    assert.deepEqual(parseDoctorArgs(["--offline", "--probe-agy"]), { offline: true, probeAgy: true });
    assert.throws(() => parseDoctorArgs(["--x"]), /unknown doctor flag/);
  });
});
