/** Names that must never appear as values in dump output. */
const SECRET_NAME = /KEY|SECRET|TOKEN|PASSWORD/i;

export function isSecretEnvName(name: string): boolean {
  return SECRET_NAME.test(name);
}

/** Refs only. Never the secret value. */
export function formatEnvRefs(env: NodeJS.ProcessEnv = process.env): string[] {
  return Object.keys(env)
    .filter(isSecretEnvName)
    .sort()
    .map((name) => `  ${name}=${env[name] ? "set" : "unset"}`);
}

/** Drop secret-shaped keys before spawning a child that should not inherit them. */
export function scrubSpawnEnv(env: NodeJS.ProcessEnv = process.env): NodeJS.ProcessEnv {
  const next: NodeJS.ProcessEnv = {};
  for (const [name, value] of Object.entries(env)) {
    if (isSecretEnvName(name)) continue;
    next[name] = value;
  }
  return next;
}
