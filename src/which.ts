import { spawnSync } from "node:child_process";

export function which(bin: string): string | undefined {
  const direct = spawnSync("which", [bin], { encoding: "utf8" });
  const found = (direct.stdout ?? "").trim();
  if (direct.status === 0 && found) return found;
  const fallback = spawnSync("/bin/sh", ["-c", `command -v ${JSON.stringify(bin)}`], {
    encoding: "utf8",
  });
  const viaShell = (fallback.stdout ?? "").trim();
  return fallback.status === 0 && viaShell ? viaShell : undefined;
}
