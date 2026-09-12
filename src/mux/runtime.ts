/** Thin client for mrh-runtime, the multiplexer in runtime/ (PLAN v3 line 35: the live wall). */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { resolve, sep } from "node:path";

import { appRoot } from "../py.ts";
import { which } from "../which.ts";

export const MUX_NAME = "mrh-runtime";

/** Where the built binary lands: <repo>/runtime/target/release/mrh-runtime. */
export function treeBinaryPath(root = appRoot()): string {
  return resolve(root, "runtime", "target", "release", MUX_NAME);
}

export type MuxSource = "MRH_RUNTIME_BIN" | "runtime/target/release" | "PATH";

export type MuxResolution = { path?: string; source?: MuxSource };

export type ResolveMuxOptions = {
  env?: NodeJS.ProcessEnv;
  root?: string;
  exists?: (path: string) => boolean;
  which?: (bin: string) => string | undefined;
};

/**
 * MRH_RUNTIME_BIN wins; then the binary built in the tree; then mrh-runtime on PATH.
 * Nothing else is ever chosen, whatever else is installed.
 */
export function resolveMux(opts: ResolveMuxOptions = {}): MuxResolution {
  const env = opts.env ?? process.env;
  const fromEnv = env.MRH_RUNTIME_BIN?.trim();
  if (fromEnv) return { path: fromEnv, source: "MRH_RUNTIME_BIN" };
  const tree = treeBinaryPath(opts.root);
  if ((opts.exists ?? existsSync)(tree)) return { path: tree, source: "runtime/target/release" };
  const onPath = (opts.which ?? which)(MUX_NAME);
  if (onPath) return { path: onPath, source: "PATH" };
  return {};
}

export function resolveMuxPath(opts: ResolveMuxOptions = {}): string | undefined {
  return resolveMux(opts).path;
}

export function muxBin(): string {
  return resolveMuxPath() || MUX_NAME;
}

/** The runtime keeps its sockets under ~/.config/mrh-runtime; HERDR_SOCKET_PATH may point at one of them. */
export const CONFIG_DIR_REL = ".config/mrh-runtime";

/** HERDR_SOCKET_PATH when set, else the default socket in the config dir. */
export function socketPath(env: NodeJS.ProcessEnv = process.env, home = homedir()): string {
  return env.HERDR_SOCKET_PATH?.trim() || resolve(home, CONFIG_DIR_REL, "herdr.sock");
}

/** True when HERDR_SOCKET_PATH is set and names a socket outside ~/.config/mrh-runtime/: some other program's server. */
export function socketIsForeign(env: NodeJS.ProcessEnv = process.env, home = homedir()): boolean {
  const set = env.HERDR_SOCKET_PATH?.trim();
  if (!set) return false;
  const dir = resolve(home, CONFIG_DIR_REL) + sep;
  return !resolve(set).startsWith(dir);
}

export type MuxResult = {
  id?: string;
  result?: Record<string, unknown>;
  error?: { code?: string; message?: string };
};

/** JSON on success or error; `pane run` and `pane send-keys` print nothing and exit 0 on success. */
export function parseMuxOutput(text: string, status: number | null): MuxResult {
  const trimmed = text.trim();
  if (!trimmed) return status === 0 ? {} : { error: { message: `no output (status ${status})` } };
  try {
    return JSON.parse(trimmed) as MuxResult;
  } catch {
    return { error: { message: trimmed } };
  }
}

export function muxRaw(args: string[]): { parsed: MuxResult; text: string; status: number | null } {
  const proc = spawnSync(muxBin(), args, { encoding: "utf8", maxBuffer: 8 * 1024 * 1024 });
  if (proc.error) {
    return { parsed: { error: { message: proc.error.message } }, text: proc.error.message, status: null };
  }
  const text = `${proc.stdout ?? ""}${proc.stderr ?? ""}`.trim();
  return { parsed: parseMuxOutput(text, proc.status), text, status: proc.status };
}

export function runMux(args: string[]): MuxResult {
  const { parsed, text } = muxRaw(args);
  if (parsed.error) {
    const msg = parsed.error.message ?? parsed.error.code ?? text;
    throw new Error(`${MUX_NAME} ${args.join(" ")}: ${msg}`);
  }
  return parsed;
}

export type ServerStatus = {
  running: boolean;
  version?: string;
  protocol?: string;
  compatible?: string;
};

/** Parse `status server` text: a dead server prints `status: not running` with exit 0. */
export function parseServerStatus(text: string, exitStatus: number | null = 0): ServerStatus {
  const out: ServerStatus = { running: false };
  if (exitStatus !== 0) return out;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    const match = line.match(/^([a-z_ -]+):\s*(.*)$/i);
    if (!match) continue;
    const key = match[1]!.trim().toLowerCase();
    const value = match[2]!.trim();
    if (key === "status") out.running = /^running\b/i.test(value);
    else if (key === "version") out.version = value;
    else if (key === "protocol") out.protocol = value;
    else if (key === "compatible") out.compatible = value;
  }
  return out;
}

export function serverStatus(): ServerStatus {
  const proc = spawnSync(muxBin(), ["status", "server"], { encoding: "utf8" });
  if (proc.error) return { running: false };
  return parseServerStatus(`${proc.stdout ?? ""}${proc.stderr ?? ""}`, proc.status);
}

export function muxAvailable(): boolean {
  return serverStatus().running;
}

export function muxOnPath(): boolean {
  const proc = spawnSync(muxBin(), ["--help"], { encoding: "utf8" });
  return !proc.error && proc.status === 0;
}

/** First line of `<mux> --version`, or undefined. */
export function muxVersion(bin = muxBin()): string | undefined {
  const proc = spawnSync(bin, ["--version"], { encoding: "utf8" });
  if (proc.error || proc.status !== 0) return undefined;
  return `${proc.stdout ?? ""}${proc.stderr ?? ""}`.trim().split(/\r?\n/)[0] || undefined;
}

/** One visible pane bound to a name, with the run's environment; never focused. */
export function paneCreateArgs(bind: string, cwd: string, env: Record<string, string>): string[] {
  return [
    "pane",
    "create",
    "--crew",
    "--bind",
    bind,
    "--cwd",
    cwd,
    ...Object.entries(env).flatMap(([key, value]) => ["--env", `${key}=${value}`]),
    "--no-focus",
  ];
}

/** Send one already-rendered shell command line to a pane. */
export function paneRun(paneId: string, cmd: string): void {
  const { parsed, text, status } = muxRaw(["pane", "run", paneId, cmd]);
  if (status === 0 && !parsed.error) return;
  const msg = parsed.error?.message ?? parsed.error?.code ?? (text || `status ${status}`);
  throw new Error(`${MUX_NAME} pane run ${paneId}: ${msg}`);
}

/** Raw pane text. `agent read` prints UTF-8, not JSON. */
export function readAgentPane(name: string, lines = 12): string {
  const handle = name.trim();
  if (!handle) return "";
  const proc = spawnSync(
    muxBin(),
    ["agent", "read", handle, "--source", "recent-unwrapped", "--lines", String(lines)],
    { encoding: "utf8", maxBuffer: 8 * 1024 * 1024 },
  );
  if (proc.error) return "";
  return (proc.stdout ?? "").trim();
}

/** Raw pane text by pane id, no agent detection needed: `pane read --source visible` prints UTF-8, not JSON. */
export function readPaneText(paneId: string, lines = 12): string {
  const handle = paneId.trim();
  if (!handle) return "";
  const proc = spawnSync(muxBin(), ["pane", "read", handle, "--source", "visible", "--lines", String(lines)], {
    encoding: "utf8",
    maxBuffer: 8 * 1024 * 1024,
  });
  if (proc.error || proc.status !== 0) return "";
  return (proc.stdout ?? "").trim();
}

/** ctrl+c to a pane by id; the agent verbs answer agent_not_found for a pane with no detected agent. */
export function paneSendKeys(paneId: string, key = "ctrl+c"): void {
  runMux(["pane", "send-keys", paneId, key]);
}

export type KillMethod = "stop" | "release" | "send-keys";

export type KillOutcome = {
  name: string;
  method: KillMethod;
  result: MuxResult;
};

export type KillAgentDeps = {
  help?: () => string;
  run?: (args: string[]) => MuxResult;
};

export function agentHelpText(): string {
  for (const args of [["agent", "--help"], ["agent"]] as const) {
    const proc = spawnSync(muxBin(), [...args], { encoding: "utf8" });
    if (proc.error) continue;
    const text = `${proc.stdout ?? ""}${proc.stderr ?? ""}`.trim();
    if (text) return text;
  }
  return "";
}

/** The installed multiplexer exposes only send-keys; stop/release are used when the help lists them. */
export function killVerbsFromHelp(help: string): KillMethod[] {
  const found = new Set<KillMethod>();
  for (const line of help.split(/\r?\n/)) {
    const match = line.match(/\bagent\s+(stop|release|send-keys)\b/i) ?? line.match(/^\s*(stop|release|send-keys)\b/i);
    if (match) found.add(match[1]!.toLowerCase() as KillMethod);
  }
  return (["stop", "release", "send-keys"] as const).filter((verb) => found.has(verb));
}

export function killAgent(name: string, deps: KillAgentDeps = {}): KillOutcome {
  const handle = name.trim();
  if (!handle) throw new Error("killAgent needs a name");
  const verbs = killVerbsFromHelp(deps.help?.() ?? agentHelpText());
  if (verbs.length === 0) {
    throw new Error(`${MUX_NAME} has no agent stop, release, or send-keys. Cannot stop ${handle}.`);
  }
  const method = verbs[0]!;
  const args = method === "send-keys" ? ["agent", "send-keys", handle, "ctrl+c"] : ["agent", method, handle];
  const run = deps.run ?? ((argv: string[]) => runMux(argv));
  return { name: handle, method, result: run(args) };
}
