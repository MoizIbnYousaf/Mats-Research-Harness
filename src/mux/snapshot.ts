import { runMux, readAgentPane } from "./runtime.ts";
import { attachLastLines, buildRoster, collectLastLineReads } from "./roster.ts";
import type { LaunchRecord, RosterRow } from "./types.ts";

export type LiveRosterDeps = {
  agents?: unknown[];
  launches?: LaunchRecord[];
  read?: (target: string) => unknown;
  readLimit?: number;
};

/** Overlay pane tails onto an already-built (and maybe filtered) roster. */
export function hydrateRosterTails(rows: RosterRow[], deps: Pick<LiveRosterDeps, "read" | "readLimit"> = {}): RosterRow[] {
  return attachLastLines(rows, collectLastLineReads(rows, deps.read ?? readAgentPane, deps.readLimit ?? 4));
}

export function listAgents(): unknown[] {
  const listed = runMux(["agent", "list"]);
  const rows = listed.result?.agents;
  return Array.isArray(rows) ? rows : [];
}

/** Live roster with last-line from event or pane. Inject list/read in tests. */
export function loadLiveRoster(deps: LiveRosterDeps = {}): RosterRow[] {
  const agents = deps.agents ?? listAgents();
  return hydrateRosterTails(buildRoster(agents, deps.launches ?? []), deps);
}
