import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import type { Body, ComposeOptions, Launch } from "../src/bodies.ts";

export const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function fixtureLaunches(): Record<Body, Launch> {
  return JSON.parse(readFileSync(resolve(REPO, "tests", "fixtures", "launch.json"), "utf8")) as Record<Body, Launch>;
}

/** compose() stand-in: the fixture for that body, cwd/proxy/model taken from the request. */
export function fixtureCompose(opts: ComposeOptions): Launch {
  const base = fixtureLaunches()[opts.body];
  return { ...base, cwd: opts.work, proxy: base.native ? null : opts.proxy, model: base.native ? base.model : opts.model };
}

export function capture(): { write: (text: string) => void; text: () => string } {
  const chunks: string[] = [];
  return { write: (text) => chunks.push(text), text: () => chunks.join("") };
}
