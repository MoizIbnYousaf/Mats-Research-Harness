/** mrh watch: the hand runs inside the live wall (PLAN v3 line 35 and line 75). */
import { spawnSync } from "node:child_process";
import { readFileSync, realpathSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import {
  composeLaunch,
  DEFAULT_MODEL,
  parseBodies,
  TASK_PLACEHOLDER,
  type Body,
  type ComposeOptions,
  type Launch,
} from "./bodies.ts";
import { checkProxyHealth, proxyUrl } from "./doctor.ts";
import { parseLevel, parseState, readTaskHeader } from "./dump.ts";
import {
  runMux,
  muxAvailable,
  killAgent,
  MUX_NAME,
  paneCreateArgs,
  paneRun,
  paneSendKeys,
  readPaneText,
  type MuxResult,
} from "./mux/runtime.ts";
import { planCrewLayout } from "./mux/layout.ts";
import { filterRoster } from "./mux/compare.ts";
import { listAgents, loadLiveRoster } from "./mux/snapshot.ts";
import type { LaunchRecord } from "./mux/types.ts";
import { formatWall, WALL_REFRESH_MS } from "./mux/wall.ts";
import { appRoot, resolvePython } from "./py.ts";

const CTRL_C = "\u0003";

export type WatchArgs = {
  task: string;
  bodies: Body[];
  model: string;
  state: string;
  level: string;
  out: string;
  dryRun: boolean;
};

export function parseWatchArgs(argv: string[]): WatchArgs {
  let task: string | undefined;
  let bodies: string | undefined;
  let model = DEFAULT_MODEL;
  let state = "A";
  let level = "1";
  let out = resolve(appRoot(), "study", "samples", "hand-runs");
  let dryRun = false;
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i]!;
    const value = (flag: string) => {
      if (token.startsWith(`${flag}=`)) return token.slice(flag.length + 1);
      const next = argv[++i];
      if (next === undefined) throw new Error(`${flag} needs a value`);
      return next;
    };
    const is = (flag: string) => token === flag || token.startsWith(`${flag}=`);
    if (is("--bodies")) bodies = value("--bodies");
    else if (is("--model")) model = value("--model");
    else if (is("--state")) state = parseState(value("--state"));
    else if (is("--level")) level = parseLevel(value("--level"));
    else if (is("--out")) out = resolve(value("--out"));
    else if (token === "--dry-run") dryRun = true;
    else if (token.startsWith("-")) throw new Error(`unknown watch flag: ${token}`);
    else if (task === undefined) task = token;
    else throw new Error(`watch takes one TASK_DIR; extra argument ${token}`);
  }
  if (!task) throw new Error("watch needs TASK_DIR");
  return { task: resolve(task), bodies: parseBodies(bodies), model, state, level, out, dryRun };
}

const SAFE_TOKEN = /^[A-Za-z0-9_@%+=:,.\/-]+$/;

/** POSIX single-quoting; plain tokens stay bare. */
export function shellQuote(text: string): string {
  if (text.length > 0 && SAFE_TOKEN.test(text)) return text;
  return `'${text.replace(/'/g, `'\\''`)}'`;
}

function singleQuote(text: string): string {
  return `'${text.replace(/'/g, `'\\''`)}'`;
}

/**
 * The pane command: every element quoted; the task element reads the prompt file so multi-line text is never typed.
 * With `stdoutLog`, stdout is also written there (`tee`), the record run.py's launch() would have kept: Antigravity's
 * stream-json has no other copy.
 */
export function renderPaneCommand(argv: string[], promptFile: string, stdoutLog?: string): string {
  const cmd = argv
    .map((element) => (element === TASK_PLACEHOLDER ? `"$(cat ${singleQuote(promptFile)})"` : shellQuote(element)))
    .join(" ");
  if (!stdoutLog) return cmd;
  return `mkdir -p ${shellQuote(resolve(stdoutLog, ".."))} && ${cmd} | tee ${shellQuote(stdoutLog)}`;
}

/** What run.py --prepare-only prints for one hand run. */
export type Prep = {
  prep_json: string;
  run_id: string;
  work: string;
  home: string;
  wroot: string;
  prompt_file: string;
  out_dir: string;
  argv: string[];
  env: Record<string, string>;
  native: boolean;
};

export type PrepareRequest = {
  task: string;
  body: Body;
  state: string;
  level: string;
  model: string;
  out: string;
};

export function parsePrep(text: string, body: Body): Prep {
  const candidates = [text.trim(), ...text.trim().split(/\r?\n/).reverse()];
  for (const candidate of candidates) {
    if (!candidate.startsWith("{")) continue;
    try {
      const rec = JSON.parse(candidate) as Record<string, unknown>;
      const str = (key: string) => (typeof rec[key] === "string" ? (rec[key] as string) : "");
      const argv = Array.isArray(rec.argv) ? rec.argv.filter((v): v is string => typeof v === "string") : [];
      if (!str("prep_json") || argv.length === 0) continue;
      const env: Record<string, string> = {};
      const rawEnv = rec.env && typeof rec.env === "object" ? (rec.env as Record<string, unknown>) : {};
      for (const [k, v] of Object.entries(rawEnv)) env[k] = String(v);
      return {
        prep_json: str("prep_json"),
        run_id: str("run_id") || body,
        work: str("work"),
        home: str("home"),
        wroot: str("wroot"),
        prompt_file: str("prompt_file"),
        out_dir: str("out_dir"),
        argv,
        env,
        native: Boolean(rec.native),
      };
    } catch {
      continue;
    }
  }
  throw new Error(`run.py --prepare-only printed no prep JSON for ${body}: ${text.trim().slice(0, 200)}`);
}

/**
 * `<python> study/runner/run.py --prepare-only --sandbox host ...`: fresh work dir, isolated HOME, prompt.md, manifest
 * skeleton. The pane runs the body on the host, so the manifest says so.
 */
export function prepareHandRun(
  req: PrepareRequest,
  opts: { root?: string; python?: string; env?: NodeJS.ProcessEnv } = {},
): Prep {
  const root = opts.root ?? appRoot();
  const env = opts.env ?? process.env;
  const python = opts.python ?? resolvePython(env, { root });
  const args = [
    resolve(root, "study", "runner", "run.py"),
    "--prepare-only",
    "--sandbox",
    "host",
    "--task",
    req.task,
    "--body",
    req.body,
    "--state",
    req.state,
    "--level",
    req.level,
    "--model",
    req.model,
    "--out",
    req.out,
  ];
  const proc = spawnSync(python, args, { cwd: root, env, encoding: "utf8", maxBuffer: 8 * 1024 * 1024 });
  if (proc.error) throw new Error(`${python}: ${proc.error.message}`);
  if (proc.status !== 0) {
    const tail = `${proc.stderr ?? ""}`.trim().split(/\r?\n/).slice(-3).join(" | ");
    throw new Error(`run.py --prepare-only failed for ${req.body} (status ${proc.status}): ${tail}`);
  }
  return parsePrep(proc.stdout ?? "", req.body);
}

/** run.py --prepare-only prints argv with the instruction text in place; put the placeholder back so the pane reads the file. */
export function placeholderArgv(argv: string[], promptText: string | undefined): string[] {
  if (argv.includes(TASK_PLACEHOLDER) || !promptText?.trim()) return argv;
  const wanted = promptText.trim();
  return argv.map((element) => (element.trim() === wanted ? TASK_PLACEHOLDER : element));
}

function readTextOrUndefined(path: string): string | undefined {
  try {
    return readFileSync(path, "utf8");
  } catch {
    return undefined;
  }
}

/** Dry-run: the same fields synthesised from the composed launch, no run.py call, nothing written. */
export function dryPrep(body: Body, launch: Launch, wroot: string, out: string): Prep {
  return {
    prep_json: resolve(wroot, "prep.json"),
    run_id: `dry-${body}`,
    work: resolve(wroot, "work"),
    home: resolve(wroot, "home"),
    wroot,
    prompt_file: resolve(wroot, "prompt.md"),
    out_dir: resolve(out, `dry-${body}`),
    argv: launch.argv,
    env: launch.env,
    native: launch.native,
  };
}

export function paneLabel(body: Body, taskId: string, state: string, level: string): string {
  return `${body} · ${taskId} · ${state}${level}`;
}

export function agentOnPane(agents: unknown, paneId: string): string | undefined {
  if (!Array.isArray(agents)) return undefined;
  for (const item of agents) {
    const rec = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
    if (rec.pane_id !== paneId) continue;
    const name = [rec.name, rec.title, rec.label].find((v) => typeof v === "string" && v) as string | undefined;
    return name ?? paneId;
  }
  return undefined;
}

export type WatchDeps = {
  compose?: (opts: ComposeOptions) => Launch;
  prepare?: (req: PrepareRequest) => Prep;
  health?: (url: string) => Promise<{ ok: boolean; detail: string }>;
  serverRunning?: () => boolean;
  mux?: (args: string[]) => MuxResult;
  paneRun?: (paneId: string, cmd: string) => void;
  listAgents?: () => unknown[];
  readPane?: (target: string) => unknown;
  readPrompt?: (path: string) => string | undefined;
  kill?: (name: string) => void;
  paneKill?: (paneId: string) => void;
  stamp?: (prepJson: string, startedAt: number) => void;
  sleep?: (ms: number) => Promise<void>;
  write?: (text: string) => void;
  error?: (text: string) => void;
  keys?: (onKey: (key: string) => void) => () => void;
  env?: NodeJS.ProcessEnv;
  now?: () => number;
  agentWaitMs?: number;
};

function defaultSleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

/** Raw-mode key reader; returns a stop function. No-op when stdin is not a TTY. */
function defaultKeys(onKey: (key: string) => void): () => void {
  const stdin = process.stdin;
  if (!stdin.isTTY) return () => {};
  stdin.setRawMode(true);
  stdin.resume();
  stdin.setEncoding("utf8");
  const handler = (chunk: string) => onKey(chunk);
  stdin.on("data", handler);
  return () => {
    stdin.off("data", handler);
    if (stdin.isTTY) stdin.setRawMode(false);
    stdin.pause();
  };
}

export function paneIdFrom(result: MuxResult): string {
  const pane = result.result?.pane;
  const rec = pane && typeof pane === "object" ? (pane as Record<string, unknown>) : {};
  const id = rec.pane_id ?? rec.id ?? result.result?.pane_id;
  if (typeof id !== "string" || !id) throw new Error(`${MUX_NAME} pane create returned no pane_id`);
  return id;
}

/** The cwd the multiplexer reports for the created pane, or undefined when it reports none. */
export function paneCwdFrom(result: MuxResult): string | undefined {
  const pane = result.result?.pane;
  const rec = pane && typeof pane === "object" ? (pane as Record<string, unknown>) : {};
  return typeof rec.cwd === "string" && rec.cwd ? rec.cwd : undefined;
}

function realpathOrSelf(path: string): string {
  try {
    return realpathSync(path);
  } catch {
    return resolve(path);
  }
}

/** True when the pane's reported cwd is the work dir (realpath on both sides: /tmp is /private/tmp on macOS). */
export function paneInWorkDir(paneCwd: string | undefined, work: string): boolean {
  if (paneCwd === undefined) return true;
  return realpathOrSelf(paneCwd) === realpathOrSelf(work);
}

/** `started` into prep.json's manifest so `run.py --finish` keeps it and stamps only `ended`. */
export function stampStarted(prepJson: string, startedAt: number): void {
  const rec = JSON.parse(readFileSync(prepJson, "utf8")) as Record<string, unknown>;
  const manifest = rec.manifest && typeof rec.manifest === "object" ? (rec.manifest as Record<string, unknown>) : {};
  manifest.started = startedAt / 1000;
  rec.manifest = manifest;
  writeFileSync(prepJson, `${JSON.stringify(rec, null, 2)}\n`);
}

export async function runWatch(argv: string[], deps: WatchDeps = {}): Promise<number> {
  const args = parseWatchArgs(argv);
  const env = deps.env ?? process.env;
  const write = deps.write ?? ((text: string) => process.stdout.write(text));
  const error = deps.error ?? ((text: string) => process.stderr.write(text));
  const compose = deps.compose ?? composeLaunch;
  const prepare = deps.prepare ?? ((req: PrepareRequest) => prepareHandRun(req, { env }));
  const health = deps.health ?? checkProxyHealth;
  const serverRunning = deps.serverRunning ?? muxAvailable;
  const mux = deps.mux ?? runMux;
  const runPane = deps.paneRun ?? paneRun;
  const agents = deps.listAgents ?? listAgents;
  const readPane = deps.readPane ?? ((target: string) => readPaneText(target, 12));
  const readPrompt = deps.readPrompt ?? readTextOrUndefined;
  const kill = deps.kill ?? ((name: string) => void killAgent(name));
  const paneKill = deps.paneKill ?? ((paneId: string) => paneSendKeys(paneId, "ctrl+c"));
  const stamp = deps.stamp ?? stampStarted;
  const sleep = deps.sleep ?? defaultSleep;
  const keys = deps.keys ?? defaultKeys;
  const now = deps.now ?? (() => Date.now());
  const proxy = proxyUrl(env);
  const header = readTaskHeader(args.task);

  if (!args.dryRun) {
    const h = await health(proxy);
    if (!h.ok) {
      error(`watch: proxy ${proxy}/health not reachable (${h.detail}); start study/runner/proxy.py first\n`);
      return 1;
    }
    if (!serverRunning()) {
      error(`watch: ${MUX_NAME} server not running; start ${MUX_NAME} first\n`);
      return 1;
    }
  }

  const layout = planCrewLayout(args.bodies.length);
  const preps: Prep[] = args.bodies.map((body) => {
    if (args.dryRun) {
      const wroot = resolve(env.HS_WORK_ROOT?.trim() || "/tmp/hs-work", `dry-${body}`);
      const launch = compose({
        body,
        model: args.model,
        home: resolve(wroot, "home"),
        work: resolve(wroot, "work"),
        proxy,
        runToken: "hs_dry",
        taskPlaceholder: TASK_PLACEHOLDER,
      });
      return dryPrep(body, launch, wroot, args.out);
    }
    const prep = prepare({ task: args.task, body, state: args.state, level: args.level, model: args.model, out: args.out });
    return { ...prep, argv: placeholderArgv(prep.argv, readPrompt(prep.prompt_file)) };
  });

  const launches: LaunchRecord[] = [];
  const planLine = (parts: string[]) => `${MUX_NAME} ${parts.map(shellQuote).join(" ")}\n`;

  /** A headless session starts with no workspace and `pane create` answers "no active workspace"; make one. */
  const ensureWorkspace = (cwd: string, label: string): void => {
    const listed = mux(["workspace", "list"]).result?.workspaces;
    if (!Array.isArray(listed) || listed.length > 0) return;
    mux(["workspace", "create", "--cwd", cwd, "--label", label, "--no-focus"]);
  };

  /** A fresh workspace hands its root pane to the first `pane create`, and that pane ignores --cwd and --env. */
  const createPane = (createArgs: string[], work: string): string => {
    let result = mux(createArgs);
    if (!paneInWorkDir(paneCwdFrom(result), work)) result = mux(createArgs);
    const cwd = paneCwdFrom(result);
    if (!paneInWorkDir(cwd, work)) {
      throw new Error(`${MUX_NAME} pane create returned ${paneIdFrom(result)} in ${cwd}, not the work dir ${work}`);
    }
    return paneIdFrom(result);
  };

  let printed = 0;
  try {
    if (!args.dryRun && preps.length > 0) ensureWorkspace(dirname(preps[0]!.wroot), `mrh watch ${header.id}`);
    for (const [index, body] of args.bodies.entries()) {
      const prep = preps[index]!;
      const bind = layout.binds[index]!;
      const createArgs = paneCreateArgs(bind, prep.work, prep.env);
      const cmd = renderPaneCommand(prep.argv, prep.prompt_file, resolve(prep.out_dir, "stdout.log"));
      const label = paneLabel(body, header.id, args.state, args.level);
      if (args.dryRun) {
        const paneId = `<pane${index}>`;
        write(planLine(createArgs));
        write(`${MUX_NAME} pane run ${paneId} ${cmd}\n`);
        write(`${MUX_NAME} pane rename ${paneId} ${shellQuote(label)}\n`);
        launches.push({ run_id: prep.run_id, body, pane_id: paneId, prep_json: prep.prep_json });
        write(`prep: ${prep.prep_json}\n`);
        continue;
      }
      const paneId = createPane(createArgs, prep.work);
      runPane(paneId, cmd);
      const startedAt = now();
      try {
        stamp(prep.prep_json, startedAt);
      } catch (err) {
        error(`watch: could not stamp started into ${prep.prep_json}: ${err instanceof Error ? err.message : String(err)}\n`);
      }
      write(`prep: ${prep.prep_json}\n`);
      printed += 1;
      const deadline = now() + (deps.agentWaitMs ?? 15_000);
      while (now() < deadline) {
        if (agentOnPane(agents(), paneId)) break;
        await sleep(300);
      }
      try {
        mux(["pane", "rename", paneId, label]);
      } catch {
        // the label is chrome; the launch stands
      }
      launches.push({
        run_id: prep.run_id,
        body,
        pane_id: paneId,
        prep_json: prep.prep_json,
        createdAt: new Date(startedAt).toISOString(),
      });
    }
  } catch (err) {
    for (const prep of preps.slice(printed)) write(`prepared, not launched: ${prep.prep_json}\n`);
    throw err;
  }

  write("finish with: mrh run --finish <prep.json>   (one per prep line; archives into the --out dir)\n");
  if (args.dryRun) return 0;

  const paneIds = launches.map((launch) => launch.pane_id);
  let stop = false;
  const stopKeys = keys((key) => {
    if (key === "q" || key === CTRL_C) stop = true;
  });
  const onSignal = () => {
    stop = true;
  };
  process.once("SIGINT", onSignal);
  try {
    while (!stop) {
      const rows = filterRoster(
        loadLiveRoster({ agents: agents(), launches, read: readPane, readLimit: paneIds.length }),
        { paneIds },
      );
      const wall = formatWall(rows, { title: `mrh watch ${header.id}`, model: args.model, now: now() });
      write(`\x1b[2J\x1b[3J\x1b[H${wall}\n  q to stop every pane\n`);
      await sleep(WALL_REFRESH_MS);
    }
  } finally {
    stopKeys();
    process.off("SIGINT", onSignal);
  }
  for (const launch of launches) {
    const agent = agentOnPane(agents(), launch.pane_id);
    try {
      if (agent) kill(agent);
      else paneKill(launch.pane_id);
    } catch (err) {
      error(`watch: could not stop ${launch.body}: ${err instanceof Error ? err.message : String(err)}\n`);
    }
  }
  return 0;
}
