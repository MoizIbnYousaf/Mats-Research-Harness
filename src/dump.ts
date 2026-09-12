/** mrh dump: the launch line per body, nothing executed or written (PLAN v3 lines 26 and 33). */
import { existsSync, readFileSync } from "node:fs";
import { basename, resolve } from "node:path";

import {
  composeLaunch,
  DEFAULT_MODEL,
  parseBodies,
  redactLaunch,
  TASK_PLACEHOLDER,
  type Body,
  type ComposeOptions,
  type Launch,
} from "./bodies.ts";
import { proxyUrl } from "./doctor.ts";
import { isSecretEnvName } from "./env.ts";

export const STATES = ["A", "B", "fixable"] as const;
export const LEVELS = ["1", "2", "3"] as const;

export type DumpArgs = {
  bodies: Body[];
  model: string;
  task: string;
  json: boolean;
};

function takeValue(argv: string[], index: number, flag: string): string {
  const token = argv[index]!;
  if (token.startsWith(`${flag}=`)) return token.slice(flag.length + 1);
  const next = argv[index + 1];
  if (next === undefined) throw new Error(`${flag} needs a value`);
  return next;
}

function isFlagWithValue(token: string, flag: string): boolean {
  return token === flag || token.startsWith(`${flag}=`);
}

export function parseState(value: string): string {
  if (!(STATES as readonly string[]).includes(value)) throw new Error(`--state needs one of ${STATES.join("|")}`);
  return value;
}

export function parseLevel(value: string): string {
  if (!(LEVELS as readonly string[]).includes(value)) throw new Error(`--level needs one of ${LEVELS.join("|")}`);
  return value;
}

export function parseDumpArgs(argv: string[]): DumpArgs {
  let bodies: string | undefined;
  let model = DEFAULT_MODEL;
  let task: string | undefined;
  let json = false;
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i]!;
    const consumed = (flag: string) => {
      const value = takeValue(argv, i, flag);
      if (!token.includes("=")) i += 1;
      return value;
    };
    if (isFlagWithValue(token, "--bodies")) bodies = consumed("--bodies");
    else if (isFlagWithValue(token, "--model")) model = consumed("--model");
    else if (isFlagWithValue(token, "--task")) task = consumed("--task");
    else if (token === "--json") json = true;
    else throw new Error(`unknown dump flag: ${token}`);
  }
  if (!task) throw new Error("dump needs --task DIR");
  return { bodies: parseBodies(bodies), model, task: resolve(task), json };
}

export type TaskHeader = { id: string; entryPoint?: string };

/** task.toml `id` and `entry_point`, read only to name the task. */
export function readTaskHeader(taskDir: string): TaskHeader {
  const toml = resolve(taskDir, "task.toml");
  if (!existsSync(toml)) throw new Error(`no task.toml in ${taskDir}`);
  const text = readFileSync(toml, "utf8");
  const id = text.match(/^\s*id\s*=\s*"([^"]*)"/m)?.[1] || basename(taskDir);
  const entryPoint = text.match(/^\s*entry_point\s*=\s*"([^"]*)"/m)?.[1];
  return entryPoint ? { id, entryPoint } : { id };
}

export function dryWorkRoot(env: NodeJS.ProcessEnv = process.env, leaf = "dry"): string {
  return resolve(env.HS_WORK_ROOT?.trim() || "/tmp/hs-work", leaf);
}

export function nativeModelLine(launch: Launch): string {
  if (!launch.native) return launch.model;
  const at = (flag: string) => {
    const i = launch.argv.indexOf(flag);
    return i >= 0 ? launch.argv[i + 1] : undefined;
  };
  const model = at("--model") ?? launch.model;
  const effort = at("--effort");
  return effort ? `${model} (effort ${effort})` : model;
}

export function formatLaunchText(launch: Launch, isSecret: (name: string) => boolean = isSecretEnvName): string[] {
  const shown = redactLaunch(launch, isSecret);
  const lines = [
    `== ${launch.body} (${launch.native ? "native" : "proxied"})`,
    `cwd: ${launch.cwd}`,
    `proxy: ${launch.native || !launch.proxy ? "none (native, account quota)" : launch.proxy}`,
    `model: ${nativeModelLine(launch)}`,
    `argv: ${launch.argv.join(" ")}`,
    "env:",
  ];
  for (const name of Object.keys(shown.env).sort()) lines.push(`  ${name}=${shown.env[name]}`);
  lines.push("files:");
  for (const file of launch.files) lines.push(`  ${file.path} (${Buffer.byteLength(file.content, "utf8")} bytes)`);
  return lines;
}

/** The launch lines do not depend on state or level (PLAN line 26), so the header names only the task. */
export function formatDump(header: TaskHeader, launches: Launch[], isSecret = isSecretEnvName): string {
  const parts = [`task: ${header.id}`];
  if (header.entryPoint) parts.push(`entry_point ${header.entryPoint}`);
  const head = parts.join("  ");
  const blocks = launches.map((launch) => formatLaunchText(launch, isSecret).join("\n"));
  return [head, ...blocks].join("\n\n");
}

export type DumpDeps = {
  compose?: (opts: ComposeOptions) => Launch;
  env?: NodeJS.ProcessEnv;
  write?: (text: string) => void;
  isSecret?: (name: string) => boolean;
};

export function runDump(argv: string[], deps: DumpDeps = {}): number {
  const args = parseDumpArgs(argv);
  const env = deps.env ?? process.env;
  const compose = deps.compose ?? composeLaunch;
  const write = deps.write ?? ((text: string) => process.stdout.write(text));
  const isSecret = deps.isSecret ?? isSecretEnvName;
  const header = readTaskHeader(args.task);
  const root = dryWorkRoot(env);
  const launches = args.bodies.map((body) =>
    compose({
      body,
      model: args.model,
      home: resolve(root, "home"),
      work: resolve(root, "work"),
      proxy: proxyUrl(env),
      runToken: "hs_dry",
      taskPlaceholder: TASK_PLACEHOLDER,
    }),
  );
  if (args.json) {
    write(`${JSON.stringify(launches.map((launch) => redactLaunch(launch, isSecret)), null, 2)}\n`);
    return 0;
  }
  write(`${formatDump(header, launches, isSecret)}\n`);
  return 0;
}
