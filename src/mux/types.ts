import type { Body } from "../bodies.ts";

export type { Body };

/** One pane on the wall, as read from the multiplexer's agent list. */
export type RosterRow = {
  name: string;
  kind: string;
  status: string;
  cwd: string;
  tabId: string;
  paneId: string;
  prompt: string;
  lastLine: string;
  createdAt: string | null;
};

/** What `mrh watch` remembers about one launched hand run (PLAN v3 line 75). */
export type LaunchRecord = {
  run_id: string;
  body: Body;
  pane_id: string;
  prep_json: string;
  createdAt?: string;
};
