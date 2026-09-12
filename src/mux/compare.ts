import type { RosterRow } from "./types.ts";

/** Wall buckets: running / idle / inactive, mapped from the multiplexer's agent_status. */
export type StatusLane = "running" | "idle" | "inactive";

export function statusLane(status: string): StatusLane {
  const key = status.toLowerCase();
  if (key === "working") return "running";
  if (key === "idle" || key === "blocked") return "idle";
  return "inactive";
}

export function countLanes(rows: RosterRow[]): Record<StatusLane, number> {
  const counts: Record<StatusLane, number> = { running: 0, idle: 0, inactive: 0 };
  for (const row of rows) counts[statusLane(row.status)] += 1;
  return counts;
}

export function filterRoster(
  rows: RosterRow[],
  opts: { kind?: string; running?: boolean; paneIds?: string[] } = {},
): RosterRow[] {
  return rows.filter((row) => {
    if (opts.kind && row.kind !== opts.kind) return false;
    if (opts.running && statusLane(row.status) !== "running") return false;
    if (opts.paneIds && !opts.paneIds.includes(row.paneId)) return false;
    return true;
  });
}

export function elapsedLabel(createdAt: string | null, now = Date.now()): string {
  if (!createdAt) return "";
  const start = Date.parse(createdAt);
  if (!Number.isFinite(start)) return "";
  const seconds = Math.max(0, Math.floor((now - start) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m${seconds % 60}s`;
  return `${Math.floor(minutes / 60)}h${minutes % 60}m`;
}
