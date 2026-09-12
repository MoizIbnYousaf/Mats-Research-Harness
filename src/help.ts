/** Usage. Each verb names the line of study/PLAN.md it serves. */
export const VERBS = ["doctor", "dump", "watch", "run", "batch", "score", "perceive", "verify", "figures"] as const;

export type Verb = (typeof VERBS)[number];

export function usage(): string {
  return `mrh: the instrument for study/PLAN.md (one model, five bodies, impossible tests)

Usage: mrh <verb> [args]

  doctor [--offline] [--probe-agy]        PLAN line 39: node, the five bodies, mrh-runtime and its server,
                                          the proxy, the key (set|unset), python with pytest, Antigravity settings.
  dump --task DIR [--bodies a,b] [--model SLUG] [--json]
                                          PLAN lines 26 and 33: the launch line per body, gates off, env with
                                          secret-shaped names as set|unset, config files written. Executes nothing.
  watch TASK_DIR [--bodies a,b] [--model SLUG] [--state S] [--level N] [--out DIR] [--dry-run]
                                          PLAN lines 35 and 75: prepare one hand run per body, one mrh-runtime
                                          pane each, the live wall until q. --dry-run prints the mux steps only.
  run ARGS                                PLAN line 35: study/runner/run.py ARGS (one run; --prepare-only, --finish).
  batch ARGS                              PLAN lines 57-68: study/runner/batch.py ARGS (blocks, concurrency, --resume).
  score RUNS_DIR | --one RUN_DIR          PLAN line 31: study/scoring/score.py (action and disclosure axes, noticed).
  perceive --runs DIR [--out CSV]         PLAN line 30: study/runner/perceive.py (what the model observed, per run).
  verify --runs DIR [--labels DIR]        PLAN line 78: study/verify.py (every headline number recomputed; VERIFY.md).
  figures --runs DIR [--out DIR]          PLAN lines 76-77: study/figures.py (fig1-3 as CSV and PNG).
  help                                    This text.

Environment: MRH_PYTHON, MRH_RUNTIME_BIN, HS_PROXY_PORT (default 8931), HS_WORK_ROOT (default /tmp/hs-work).
`;
}
