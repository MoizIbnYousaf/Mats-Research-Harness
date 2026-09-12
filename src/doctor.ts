/** mrh doctor: the uncounted checks before the kill test (PLAN v3 line 39; line 35 for mrh-runtime; Verification item 4). */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { get as httpGet } from "node:http";
import { homedir } from "node:os";
import { resolve } from "node:path";

import { BODIES, type Body } from "./bodies.ts";
import { muxVersion, resolveMux, serverStatus, socketIsForeign, socketPath, type MuxSource, type ServerStatus } from "./mux/runtime.ts";
import { resolvePython } from "./py.ts";
import { which } from "./which.ts";

export const BODY_BIN: Record<Body, string> = {
  antigravity: "agy",
  claude: "claude",
  codex: "codex",
  opencode: "opencode",
  pi: "pi",
};

export const AGY_SETTINGS_REL = ".gemini/antigravity-cli/settings.json";

export type RowStatus = "ok" | "no" | "skip";

export type DoctorRow = { status: RowStatus; name: string; detail: string };

export type BodyProbe = { path?: string; version?: string };

export type AgyProbe = {
  models: { ok: boolean; detail: string };
  wrongSlug: { ok: boolean; detail: string };
};

export type DoctorProbe = {
  node: string;
  bodies: Record<Body, BodyProbe>;
  runtime: { path?: string; source?: MuxSource; version?: string };
  /** The socket doctor and watch would talk to, and whether HERDR_SOCKET_PATH points somewhere that is not ours. */
  socket: { path: string; foreign: boolean };
  server?: ServerStatus;
  proxy: { url: string; ok?: boolean; detail?: string };
  keySet: boolean;
  python: { path: string; version?: string; pytest?: string };
  agySettings: { path: string; present: boolean };
  agy?: AgyProbe;
};

export type DoctorOptions = { offline?: boolean; probeAgy?: boolean };

export function parseDoctorArgs(argv: string[]): DoctorOptions {
  const opts: DoctorOptions = {};
  for (const token of argv) {
    if (token === "--offline") opts.offline = true;
    else if (token === "--probe-agy") opts.probeAgy = true;
    else throw new Error(`unknown doctor flag: ${token}`);
  }
  return opts;
}

export function proxyUrl(env: NodeJS.ProcessEnv = process.env): string {
  return `http://127.0.0.1:${env.HS_PROXY_PORT?.trim() || "8931"}`;
}

/** GET <url>/health with no headers beyond Host; the key is never sent. */
export function checkProxyHealth(base: string, timeoutMs = 2000): Promise<{ ok: boolean; detail: string }> {
  return new Promise((resolvePromise) => {
    let settled = false;
    const finish = (ok: boolean, detail: string) => {
      if (settled) return;
      settled = true;
      resolvePromise({ ok, detail });
    };
    let req: ReturnType<typeof httpGet>;
    try {
      req = httpGet(`${base}/health`, { headers: {}, timeout: timeoutMs }, (res) => {
        res.resume();
        const code = res.statusCode ?? 0;
        finish(code === 200, `${code}`);
      });
    } catch (error) {
      finish(false, error instanceof Error ? error.message : String(error));
      return;
    }
    req.on("timeout", () => {
      req.destroy();
      finish(false, "timeout");
    });
    req.on("error", (error) => finish(false, (error as NodeJS.ErrnoException).code ?? error.message));
  });
}

function firstLine(bin: string, args: string[]): string | undefined {
  const proc = spawnSync(bin, args, { encoding: "utf8", timeout: 15_000 });
  if (proc.error || proc.status !== 0) return undefined;
  return `${proc.stdout ?? ""}${proc.stderr ?? ""}`.trim().split(/\r?\n/)[0] || undefined;
}

function probeBody(bin: string): BodyProbe {
  const path = which(bin);
  if (!path) return {};
  return { path, version: firstLine(path, ["--version"]) };
}

function probePython(python: string): DoctorProbe["python"] {
  const version = firstLine(python, ["--version"]);
  const pytestLine = firstLine(python, ["-m", "pytest", "--version"]);
  const pytest = pytestLine?.match(/pytest\s+([\d.]+\S*)/i)?.[1];
  return { path: python, version, pytest };
}

function probeAgy(agyPath: string): AgyProbe {
  const models = spawnSync(agyPath, ["models"], { encoding: "utf8", timeout: 60_000 });
  const modelsOut = `${models.stdout ?? ""}${models.stderr ?? ""}`.trim();
  const wrong = spawnSync(agyPath, ["-p", "ping", "--model", "mrh-not-a-model", "--print-timeout", "30s"], {
    encoding: "utf8",
    timeout: 60_000,
  });
  const wrongOut = `${wrong.stdout ?? ""}${wrong.stderr ?? ""}`.trim().split(/\r?\n/).slice(-1)[0] ?? "";
  return {
    models: {
      ok: !models.error && models.status === 0 && modelsOut.length > 0,
      detail: models.error ? models.error.message : `exit ${models.status}, ${modelsOut.split(/\r?\n/).length} lines`,
    },
    wrongSlug: {
      ok: !wrong.error && wrong.status !== 0,
      detail: wrong.error ? wrong.error.message : `exit ${wrong.status} on mrh-not-a-model ${wrongOut.slice(0, 60)}`.trim(),
    },
  };
}

export async function liveDoctorProbe(opts: DoctorOptions = {}, env: NodeJS.ProcessEnv = process.env): Promise<DoctorProbe> {
  const bodies = Object.fromEntries(BODIES.map((body) => [body, probeBody(BODY_BIN[body])])) as Record<Body, BodyProbe>;
  const found = resolveMux({ env });
  const runtime = { path: found.path, source: found.source, version: found.path ? muxVersion(found.path) : undefined };
  const socket = { path: socketPath(env), foreign: socketIsForeign(env) };
  const url = proxyUrl(env);
  const proxy: DoctorProbe["proxy"] = { url };
  let server: ServerStatus | undefined;
  if (!opts.offline) {
    // A foreign socket is never probed: the answer would come from some other program's server.
    if (!socket.foreign) server = found.path ? serverStatus() : { running: false };
    const health = await checkProxyHealth(url);
    proxy.ok = health.ok;
    proxy.detail = health.detail;
  }
  const settingsPath = resolve(homedir(), AGY_SETTINGS_REL);
  const agyPath = bodies.antigravity.path;
  return {
    node: process.version,
    bodies,
    runtime,
    socket,
    server,
    proxy,
    keySet: Boolean(env.OPENROUTER_API_KEY),
    python: probePython(resolvePython(env)),
    agySettings: { path: settingsPath, present: existsSync(settingsPath) },
    agy: opts.probeAgy && !opts.offline && agyPath ? probeAgy(agyPath) : undefined,
  };
}

function tilde(path: string): string {
  const home = homedir();
  return path.startsWith(home) ? `~${path.slice(home.length)}` : path;
}

/** The rows, in order. Pure. */
export function doctorRows(probe: DoctorProbe, opts: DoctorOptions = {}): DoctorRow[] {
  const rows: DoctorRow[] = [];
  const nodeOk = /^v(2[2-9]|[3-9]\d)\./.test(probe.node);
  rows.push({ status: nodeOk ? "ok" : "no", name: "node", detail: probe.node });
  for (const body of BODIES) {
    const found = probe.bodies[body];
    rows.push({
      status: found.path ? "ok" : "no",
      name: `body ${body}`,
      detail: found.path ? `${found.path} ${found.version ?? ""}`.trim() : `${BODY_BIN[body]} missing`,
    });
  }
  rows.push({
    status: probe.runtime.path && probe.runtime.version ? "ok" : "no",
    name: "mrh-runtime",
    detail: probe.runtime.path
      ? `${probe.runtime.path} (${probe.runtime.source ?? "given"}) ${probe.runtime.version ?? "does not answer --version"}`
      : "not built (make runtime)",
  });
  const sock = tilde(probe.socket.path);
  if (probe.socket.foreign) {
    rows.push({ status: "no", name: "mrh-runtime server", detail: "HERDR_SOCKET_PATH points at another program's server; unset it" });
  } else if (opts.offline || !probe.server) {
    rows.push({ status: "skip", name: "mrh-runtime server", detail: `${sock} --offline` });
  } else if (probe.server.running) {
    const parts = [
      sock,
      "running",
      probe.server.version ? `version ${probe.server.version}` : "",
      probe.server.protocol ? `protocol ${probe.server.protocol}` : "",
      probe.server.compatible ? `compatible ${probe.server.compatible}` : "",
    ].filter(Boolean);
    rows.push({ status: "ok", name: "mrh-runtime server", detail: parts.join(" ") });
  } else {
    rows.push({ status: "no", name: "mrh-runtime server", detail: `${sock} not running` });
  }
  const health = `${probe.proxy.url}/health`;
  if (opts.offline || probe.proxy.ok === undefined) {
    rows.push({ status: "skip", name: "proxy", detail: `${health} --offline` });
  } else {
    rows.push({ status: probe.proxy.ok ? "ok" : "no", name: "proxy", detail: `${health} ${probe.proxy.detail ?? ""}`.trim() });
  }
  rows.push({ status: probe.keySet ? "ok" : "no", name: "OPENROUTER_API_KEY", detail: probe.keySet ? "set" : "unset" });
  rows.push({
    status: probe.python.version && probe.python.pytest ? "ok" : "no",
    name: "python",
    detail: `${probe.python.path} ${probe.python.version ?? "missing"} pytest ${probe.python.pytest ?? "missing"}`,
  });
  rows.push({
    status: probe.agySettings.present ? "ok" : "no",
    name: "antigravity settings",
    detail: `${tilde(probe.agySettings.path)} ${probe.agySettings.present ? "present" : "missing"}`,
  });
  if (opts.probeAgy) {
    if (opts.offline || !probe.agy) {
      const why = opts.offline ? "--offline" : "agy missing";
      rows.push({ status: "skip", name: "agy models", detail: why });
      rows.push({ status: "skip", name: "agy wrong slug", detail: why });
    } else {
      rows.push({ status: probe.agy.models.ok ? "ok" : "no", name: "agy models", detail: probe.agy.models.detail });
      rows.push({ status: probe.agy.wrongSlug.ok ? "ok" : "no", name: "agy wrong slug", detail: probe.agy.wrongSlug.detail });
    }
  }
  return rows;
}

export function formatDoctorRow(row: DoctorRow): string {
  return `${row.status.padEnd(12)}  ${row.name.padEnd(20)} ${row.detail}`.trimEnd();
}

export function doctorExitCode(rows: DoctorRow[], opts: DoctorOptions = {}): number {
  if (opts.offline) return 0;
  return rows.some((row) => row.status === "no") ? 1 : 0;
}

/** Pure: the whole report for an injected probe. */
export function formatDoctorReport(probe: DoctorProbe, opts: DoctorOptions = {}): string {
  const rows = doctorRows(probe, opts);
  const missing = rows.filter((row) => row.status === "no").length;
  const head = opts.offline ? "mrh doctor (offline: network probes skipped)" : "mrh doctor";
  const foot = opts.offline ? "doctor: offline, report only" : missing === 0 ? "doctor: ok" : `doctor: ${missing} missing`;
  return [head, ...rows.map(formatDoctorRow), foot].join("\n");
}

export async function runDoctor(argv: string[], write: (text: string) => void = (t) => process.stdout.write(t)): Promise<number> {
  const opts = parseDoctorArgs(argv);
  const probe = await liveDoctorProbe(opts);
  write(`${formatDoctorReport(probe, opts)}\n`);
  return doctorExitCode(doctorRows(probe, opts), opts);
}
