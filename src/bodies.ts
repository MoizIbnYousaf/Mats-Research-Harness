/** The five bodies (PLAN v3 line 26). Composition comes from study/runner/harness_env.py --json; nothing is hardcoded here. */
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

import { appRoot, resolvePython } from "./py.ts";

export const BODIES = ["antigravity", "claude", "codex", "opencode", "pi"] as const;
export type Body = (typeof BODIES)[number];

export const DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731";
export const TASK_PLACEHOLDER = "<task>";

export function isBody(value: string): value is Body {
  return (BODIES as readonly string[]).includes(value);
}

export function parseBodies(text: string | undefined): Body[] {
  if (!text?.trim()) return [...BODIES];
  const out: Body[] = [];
  for (const part of text.split(",").map((s) => s.trim()).filter(Boolean)) {
    if (!isBody(part)) throw new Error(`unknown body ${part}; bodies are ${BODIES.join(", ")}`);
    if (!out.includes(part)) out.push(part);
  }
  if (out.length === 0) throw new Error("--bodies needs at least one body");
  return out;
}

export type LaunchFile = { path: string; content: string };

export type Launch = {
  body: Body;
  native: boolean;
  proxy: string | null;
  model: string;
  argv: string[];
  env: Record<string, string>;
  files: LaunchFile[];
  cwd: string;
};

export type ComposeSpawn = (
  cmd: string,
  args: string[],
  opts: { cwd: string },
) => { status: number | null; stdout: string; stderr: string };

export type ComposeOptions = {
  body: Body;
  model: string;
  home: string;
  work: string;
  proxy: string;
  runToken: string;
  taskPlaceholder?: string;
  python?: string;
  root?: string;
  spawn?: ComposeSpawn;
};

function defaultSpawn(cmd: string, args: string[], opts: { cwd: string }) {
  const proc = spawnSync(cmd, args, { cwd: opts.cwd, encoding: "utf8", maxBuffer: 8 * 1024 * 1024 });
  if (proc.error) return { status: 127, stdout: "", stderr: proc.error.message };
  return { status: proc.status, stdout: proc.stdout ?? "", stderr: proc.stderr ?? "" };
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

function stringMap(value: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(asRecord(value))) {
    if (typeof v === "string") out[k] = v;
    else if (v != null) out[k] = String(v);
  }
  return out;
}

function fileList(value: unknown): LaunchFile[] {
  if (!Array.isArray(value)) return [];
  const out: LaunchFile[] = [];
  for (const item of value) {
    const rec = asRecord(item);
    if (typeof rec.path !== "string") continue;
    out.push({ path: rec.path, content: typeof rec.content === "string" ? rec.content : "" });
  }
  return out;
}

/** Parse the JSON harness_env.py --json prints for one body. */
export function parseLaunch(text: string, opts: Pick<ComposeOptions, "body" | "model" | "work">): Launch {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error(`harness_env.py --json printed no JSON for ${opts.body}: ${text.trim().slice(0, 200)}`);
  }
  const rec = asRecord(parsed);
  const body = typeof rec.body === "string" && isBody(rec.body) ? rec.body : opts.body;
  const argv = stringList(rec.argv);
  if (argv.length === 0) throw new Error(`harness_env.py --json returned no argv for ${opts.body}`);
  const native = Boolean(rec.native);
  const proxy = typeof rec.proxy === "string" && rec.proxy ? rec.proxy : null;
  return {
    body,
    native,
    proxy: native ? null : proxy,
    model: typeof rec.model === "string" && rec.model ? rec.model : opts.model,
    argv,
    env: stringMap(rec.env),
    files: fileList(rec.files),
    cwd: typeof rec.cwd === "string" && rec.cwd ? rec.cwd : opts.work,
  };
}

/** Compose args for harness_env.py --json. Never --write. */
export function composeArgs(opts: ComposeOptions, root: string): string[] {
  const args = [
    resolve(root, "study", "runner", "harness_env.py"),
    "--json",
    "--body",
    opts.body,
    "--model",
    opts.model,
    "--home",
    opts.home,
    "--work",
    opts.work,
    "--proxy",
    opts.proxy,
    "--run-token",
    opts.runToken,
    "--task-placeholder",
    opts.taskPlaceholder ?? TASK_PLACEHOLDER,
  ];
  return args;
}

/** The single composition source for dump, watch and run.py alike. */
export function composeLaunch(opts: ComposeOptions): Launch {
  const root = opts.root ?? appRoot();
  const python = opts.python ?? resolvePython(process.env, { root });
  const spawn = opts.spawn ?? defaultSpawn;
  const args = composeArgs(opts, root);
  const proc = spawn(python, args, { cwd: root });
  if (proc.status !== 0) {
    const detail = (proc.stderr || proc.stdout).trim().split(/\r?\n/).slice(-3).join(" | ");
    throw new Error(`harness_env.py --json failed for ${opts.body} (status ${proc.status}): ${detail}`);
  }
  return parseLaunch(proc.stdout, opts);
}

/** Copy of a Launch with secret-shaped env values replaced by set/unset markers. */
export function redactLaunch(launch: Launch, isSecret: (name: string) => boolean): Launch {
  const env: Record<string, string> = {};
  for (const [name, value] of Object.entries(launch.env)) {
    env[name] = isSecret(name) ? envMarker(value) : value;
  }
  return { ...launch, env };
}

/** Marker for a secret-shaped name: a run token is named as such; a real value is never printed. */
export function envMarker(value: string): string {
  if (!value) return "unset";
  if (value.startsWith("hs_")) return "set (run token, not the key)";
  return "set";
}
