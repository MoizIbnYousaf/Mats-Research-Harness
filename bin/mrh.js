#!/usr/bin/env node
process.title = "mrh";
await import(new URL("../src/index.ts", import.meta.url).href);
