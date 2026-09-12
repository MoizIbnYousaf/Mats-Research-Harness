/** Python resolution and the pass-through to study/ scripts (PLAN v3 line 35: runner; lines 30-31, 76-78). */
import { accessSync, constants } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/** Repository root: the parent of src/. */
export function appRoot(): string {
  return resolve(dirname(fileURLToPath(import.meta.url)), "..");
}

export type ResolvePythonDeps = {
  root?: string;
  executable?: (path: string) => boolean;
};

function isExecutable(path: string): boolean {
  try {
    accessSync(path, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

/** MRH_PYTHON, then study/.venv/bin/python when executable, then python3 on PATH. */
export function resolvePython(env: NodeJS.ProcessEnv = process.env, deps: ResolvePythonDeps = {}): string {
  const fromEnv = env.MRH_PYTHON?.trim();
  if (fromEnv) return fromEnv;
  const venv = resolve(deps.root ?? appRoot(), "study", ".venv", "bin", "python");
  if ((deps.executable ?? isExecutable)(venv)) return venv;
  return "python3";
}

export type RunStudyOptions = {
  python?: string;
  root?: string;
  cwd?: string;
  env?: NodeJS.ProcessEnv;
  spawn?: (cmd: string, args: string[], opts: { cwd: string; env: NodeJS.ProcessEnv }) => number;
};

function inheritSpawn(cmd: string, args: string[], opts: { cwd: string; env: NodeJS.ProcessEnv }): number {
  const proc = spawnSync(cmd, args, { cwd: opts.cwd, env: opts.env, stdio: "inherit" });
  if (proc.error) {
    console.error(`${cmd}: ${proc.error.message}`);
    return 127;
  }
  return proc.status ?? 1;
}

/**
 * `<python> study/<script> ARGS` from the caller's cwd, so relative --task/--out/--runs/RUNS_DIR arguments mean what
 * they would on the command line (the scripts locate study/ from their own path); exit code propagated.
 */
export function runStudy(script: string, args: string[], opts: RunStudyOptions = {}): number {
  const root = opts.root ?? appRoot();
  const env = opts.env ?? process.env;
  const python = opts.python ?? resolvePython(env, { root });
  const spawn = opts.spawn ?? inheritSpawn;
  return spawn(python, [resolve(root, "study", script), ...args], { cwd: opts.cwd ?? process.cwd(), env });
}
