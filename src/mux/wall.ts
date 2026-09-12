/** The live wall (PLAN v3 line 35): one box per pane, status lane, elapsed, recent lines. */
import { countLanes, elapsedLabel, statusLane, type StatusLane } from "./compare.ts";
import { recentPaneLines, rosterLastLine } from "./events.ts";
import type { RosterRow } from "./types.ts";

export const WALL_REFRESH_MS = 1000;

const LANE_ORDER: StatusLane[] = ["running", "idle", "inactive"];

const LANE_ICON: Record<StatusLane, string> = {
  running: "●",
  idle: "○",
  inactive: "·",
};

export type WallOptions = {
  maxScreens?: number;
  now?: number;
  title?: string;
  model?: string;
};

function oneLine(text: string, max: number): string {
  const flat = text.replace(/\s+/g, " ").trim();
  if (flat.length <= max) return flat;
  return `${flat.slice(0, Math.max(0, max - 1))}…`;
}

function laneRank(row: RosterRow): number {
  return LANE_ORDER.indexOf(statusLane(row.status));
}

function pickScreens(rows: RosterRow[], maxScreens: number): RosterRow[] {
  const sorted = [...rows].sort((a, b) => {
    const lane = laneRank(a) - laneRank(b);
    if (lane !== 0) return lane;
    return a.name.localeCompare(b.name);
  });
  return sorted.slice(0, maxScreens);
}

/** One box per pane. */
export function formatScreen(row: RosterRow, now = Date.now()): string[] {
  const lane = statusLane(row.status);
  const icon = LANE_ICON[lane];
  const age = elapsedLabel(row.createdAt, now);
  const head = [icon, row.kind, row.name !== row.kind ? row.name : "", lane, age].filter(Boolean).join("  ");
  const pane = row.paneId ? `  ${row.paneId}` : "";
  const lines = [`╭─ ${head}${pane}`];
  if (row.prompt.trim()) lines.push(`│ > ${oneLine(row.prompt, 70)}`);
  const tail = row.lastLine.trim()
    ? recentPaneLines(row.lastLine, 3)
    : [rosterLastLine(row)].filter((line) => line.trim());
  tail.forEach((line, index) => {
    if (!line.trim()) return;
    const hook = index < tail.length - 1 ? "├" : "·";
    lines.push(`│ ${hook} ${oneLine(line, 70)}`);
  });
  lines.push("╰─");
  return lines;
}

export function formatWall(rows: RosterRow[], options: WallOptions = {}): string {
  const lanes = countLanes(rows);
  const title = options.title?.trim() || "mrh watch";
  const counts = `${lanes.running} running · ${lanes.idle} idle · ${lanes.inactive} inactive`;
  const pin = options.model ? `  ${options.model}` : "";
  const header = `${title}  ${rows.length} panes${pin}  ${counts}`;
  if (rows.length === 0) return [header, "", "  no panes."].join("\n");

  const now = options.now ?? Date.now();
  const cap = options.maxScreens ?? rows.length;
  const shown = pickScreens(rows, cap);
  const hidden = rows.length - shown.length;
  const screens = shown.flatMap((row) => ["", ...formatScreen(row, now)]);
  const more = hidden > 0 ? ["", `  + ${hidden} more`] : [];
  return [header, ...screens, ...more].join("\n");
}
