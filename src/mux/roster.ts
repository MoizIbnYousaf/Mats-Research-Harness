import { statusLane } from "./compare.ts";
import { textFromRead } from "./events.ts";
import type { LaunchRecord, RosterRow } from "./types.ts";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/** Event JSON or last_line field from an agent-list row. */
export function lastLineHint(rec: Record<string, unknown>): string {
  if (str(rec.last_line).trim()) return str(rec.last_line);
  if (str(rec.last_output).trim()) return str(rec.last_output);
  if (str(rec.event).trim()) {
    return JSON.stringify({ event: rec.event, detail: str(rec.detail), response: str(rec.response) });
  }
  return "";
}

/** Merge the live agent list with the panes `mrh watch` launched. Unlaunched panes keep their own names. */
export function buildRoster(agents: unknown[], launches: LaunchRecord[] = []): RosterRow[] {
  const byPane = new Map<string, LaunchRecord>();
  for (const launch of launches) byPane.set(launch.pane_id, launch);

  const seen = new Set<string>();
  const rows: RosterRow[] = [];
  for (const item of agents) {
    const rec = asRecord(item);
    const paneId = str(rec.pane_id);
    const alias = str(rec.name) || str(rec.title) || str(rec.label);
    const launch = byPane.get(paneId);
    const key = paneId || alias || str(rec.agent);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    rows.push({
      name: launch?.body ?? alias ?? paneId,
      kind: launch?.body ?? (str(rec.display_agent) || str(rec.agent) || "unknown"),
      status: str(rec.agent_status) || "unknown",
      cwd: str(rec.foreground_cwd) || str(rec.cwd) || "",
      tabId: str(rec.tab_id),
      paneId,
      prompt: launch?.run_id ?? "",
      lastLine: lastLineHint(rec),
      createdAt: launch?.createdAt ?? null,
    });
  }
  for (const launch of launches) {
    if (seen.has(launch.pane_id)) continue;
    seen.add(launch.pane_id);
    rows.push({
      name: launch.body,
      kind: launch.body,
      status: "unknown",
      cwd: "",
      tabId: "",
      paneId: launch.pane_id,
      prompt: launch.run_id,
      lastLine: "",
      createdAt: launch.createdAt ?? null,
    });
  }
  return rows;
}

const LANE_RANK: Record<string, number> = { running: 0, idle: 1, inactive: 2 };

/** Read pane tails, running panes first, at most `limit` reads. Inject `read` in tests. */
export function collectLastLineReads(
  rows: RosterRow[],
  read: (target: string) => unknown,
  limit = 4,
): Record<string, unknown> {
  const ordered = [...rows].sort((a, b) => {
    const lane = (LANE_RANK[statusLane(a.status)] ?? 9) - (LANE_RANK[statusLane(b.status)] ?? 9);
    if (lane !== 0) return lane;
    return a.name.localeCompare(b.name);
  });
  const out: Record<string, unknown> = {};
  for (const row of ordered) {
    if (Object.keys(out).length >= limit) break;
    const target = row.paneId || row.name;
    if (!target || target in out) continue;
    try {
      out[target] = read(target);
    } catch {
      out[target] = "";
    }
  }
  return out;
}

/** Overlay read (or injected) pane text onto roster rows. */
export function attachLastLines(rows: RosterRow[], reads: Record<string, unknown>): RosterRow[] {
  return rows.map((row) => {
    const payload = reads[row.paneId] ?? reads[row.name];
    if (payload === undefined) return row;
    const text = textFromRead(payload);
    if (!text.trim()) return row;
    return { ...row, lastLine: text };
  });
}
