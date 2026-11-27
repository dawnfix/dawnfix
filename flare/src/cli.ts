#!/usr/bin/env node
// flare: read-only audit of Cloudflare accounts and Workers fleets. Everything is in main.ts;
// this file runs it when it is the program node was started with.

import { existsSync, realpathSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import type { FetchLike } from './core/client.js';
import { main } from './main.js';

export * from './main.js';

const invoked = process.argv[1] && existsSync(process.argv[1]) ? pathToFileURL(realpathSync(process.argv[1])).href : '';
if (import.meta.url === invoked) {
  main(process.argv.slice(2), {
    env: process.env,
    fetch: globalThis.fetch as unknown as FetchLike,
    stdout: (s) => process.stdout.write(s),
    stderr: (s) => process.stderr.write(s),
    now: () => new Date(),
    isTTY: Boolean(process.stdout.isTTY),
    ...(process.stdout.columns ? { columns: process.stdout.columns } : {}),
    cwd: process.cwd(),
  }).then((code) => process.exit(code));
}
