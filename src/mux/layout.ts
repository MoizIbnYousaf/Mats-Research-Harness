export type LayoutCreate = { op: "create"; bind: string };

export type CrewLayoutPlan = {
  binds: string[];
  steps: LayoutCreate[];
};

/** One visible pane per body, bound body0..bodyN-1. */
export function planCrewLayout(count: number): CrewLayoutPlan {
  if (!Number.isInteger(count) || count < 1) throw new Error("watch needs at least one body");
  const binds = Array.from({ length: count }, (_, index) => `body${index}`);
  return { binds, steps: binds.map((bind) => ({ op: "create", bind })) };
}
