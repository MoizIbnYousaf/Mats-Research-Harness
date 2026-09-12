import { runDoctor } from "./doctor.ts";
import { runDump, type DumpDeps } from "./dump.ts";
import { usage, VERBS } from "./help.ts";
import { runStudy } from "./py.ts";
import { runWatch, type WatchDeps } from "./watch.ts";

/** Pass-through verbs and the study script each one runs (PLAN v3 lines 30, 31, 35, 57-68, 76-78). */
export const STUDY_SCRIPT: Record<string, string> = {
  run: "runner/run.py",
  batch: "runner/batch.py",
  score: "scoring/score.py",
  perceive: "runner/perceive.py",
  verify: "verify.py",
  figures: "figures.py",
};

export type CliDeps = {
  write?: (text: string) => void;
  error?: (text: string) => void;
  dump?: DumpDeps;
  watch?: WatchDeps;
  study?: (script: string, args: string[]) => number;
};

/** Exactly the verbs in study/PLAN.md; anything else prints usage and exits 2. */
export async function main(argv: string[] = process.argv.slice(2), deps: CliDeps = {}): Promise<number> {
  const write = deps.write ?? ((text: string) => process.stdout.write(text));
  const error = deps.error ?? ((text: string) => process.stderr.write(text));
  const verb = argv[0];
  const rest = argv.slice(1);

  if (!verb) {
    error(usage());
    return 2;
  }
  if (verb === "help" || verb === "--help" || verb === "-h") {
    write(usage());
    return 0;
  }
  if (!(VERBS as readonly string[]).includes(verb)) {
    error(`mrh: unknown verb ${verb}\n\n${usage()}`);
    return 2;
  }
  try {
    if (verb === "doctor") return await runDoctor(rest, write);
    if (verb === "dump") return runDump(rest, { write, ...deps.dump });
    if (verb === "watch") return await runWatch(rest, { write, error, ...deps.watch });
    const script = STUDY_SCRIPT[verb]!;
    return (deps.study ?? runStudy)(script, rest);
  } catch (err) {
    error(`mrh ${verb}: ${err instanceof Error ? err.message : String(err)}\n`);
    return 1;
  }
}
