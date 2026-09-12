/** Last-line vocabulary for the wall: structured pane events when present, else visible pane text. */
const EVENTS = [
  "session_start",
  "prompt_submitted",
  "tool_completed",
  "needs_input",
  "permission_request",
  "task_complete",
  "task_failed",
] as const;

type PaneEvent = (typeof EVENTS)[number];

const EVENT_ALIASES: Record<string, PaneEvent> = {
  session_start: "session_start",
  user_prompt_submit: "prompt_submitted",
  post_tool_use: "tool_completed",
  idle_prompt: "needs_input",
  permission_request: "permission_request",
  stop: "task_complete",
  stop_failure: "task_failed",
};

const VERB: Record<PaneEvent, string> = {
  session_start: "started",
  prompt_submitted: "running",
  tool_completed: "tool done",
  needs_input: "needs input",
  permission_request: "needs permission",
  task_complete: "done",
  task_failed: "failed",
};

function lineForEvent(event: PaneEvent, detail = ""): string {
  const tail = detail.replace(/\s+/g, " ").trim().slice(0, 72);
  return tail ? `${VERB[event]} · ${tail}` : VERB[event];
}

function eventForStatus(status: string): PaneEvent {
  const key = status.toLowerCase();
  if (key === "working") return "prompt_submitted";
  if (key === "idle" || key === "blocked") return "needs_input";
  if (key === "done") return "task_complete";
  if (key === "failed" || key === "error") return "task_failed";
  return "session_start";
}

function coerceEvent(name: string): PaneEvent | undefined {
  const key = name.trim();
  if ((EVENTS as readonly string[]).includes(key)) return key as PaneEvent;
  return EVENT_ALIASES[key];
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function eventDetail(rec: Record<string, unknown>): string {
  return str(rec.response) || str(rec.query) || str(rec.detail) || str(rec.prompt) || str(rec.title) || str(rec.tool) || "";
}

function tryJsonObject(raw: string): Record<string, unknown> | undefined {
  try {
    return asRecord(JSON.parse(raw));
  } catch {
    return undefined;
  }
}

function jsonObjectsIn(text: string): Record<string, unknown>[] {
  const found: Record<string, unknown>[] = [];
  const whole = tryJsonObject(text.trim());
  if (whole) found.push(whole);
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) continue;
    const rec = tryJsonObject(trimmed);
    if (rec) found.push(rec);
  }
  return found;
}

function lastLineFromEventPayload(text: string): string | undefined {
  let last: string | undefined;
  for (const rec of jsonObjectsIn(text)) {
    const event = coerceEvent(str(rec.event));
    if (!event) continue;
    last = lineForEvent(event, eventDetail(rec));
  }
  return last;
}

/** Last visible pane line. */
export function lastLineFromPane(text: string): string {
  return recentPaneLines(text, 1)[0] ?? "";
}

/** Up to three recent non-empty pane lines, event lines rendered as verbs. */
export function recentPaneLines(text: string, max = 3): string[] {
  const cap = Math.min(3, Math.max(1, Math.floor(max)));
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter(Boolean);
  return lines.slice(-cap).map((line) => (lastLineFromEventPayload(line) ?? line).slice(0, 72));
}

/** Pull transcript text out of a multiplexer read (raw CLI text or socket JSON). */
export function textFromRead(payload: unknown): string {
  if (typeof payload === "string") return payload;
  const rec = asRecord(payload);
  if (!rec) return "";
  if (typeof rec.text === "string") return rec.text;
  const result = asRecord(rec.result);
  if (result) {
    if (typeof result.text === "string") return result.text;
    const read = asRecord(result.read);
    if (typeof read?.text === "string") return read.text;
  }
  if (typeof rec.event === "string") return JSON.stringify(rec);
  return "";
}

/** Event if present, else last visible pane line, else a verb for the status. */
export function rosterLastLine(row: { lastLine: string; prompt: string; status: string }): string {
  if (row.lastLine.trim()) {
    return lastLineFromEventPayload(row.lastLine) ?? lastLineFromPane(row.lastLine);
  }
  return lineForEvent(eventForStatus(row.status), row.prompt);
}
