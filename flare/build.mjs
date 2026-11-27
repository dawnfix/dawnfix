// Bundles src/cli.ts and everything it imports into one file, dist/cli.js, with no runtime
// dependency: you and the CI workflow run it with plain `node` (20 or newer).
// dist/cli.js is checked in. `npm run build` writes it; `npm run build:check` (and
// test/dist.test.ts) fail when it differs from what the sources build to.
//
//   node build.mjs            write dist/cli.js
//   node build.mjs --check    exit 1 if dist/cli.js is stale
import { build } from 'esbuild';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = dirname(fileURLToPath(import.meta.url));
export const OUT = join(ROOT, 'dist', 'cli.js');

const BANNER = `// Dawnfix Flare: read-only audit of Cloudflare accounts and Workers.
// Source available under FSL-1.1-ALv2 (see LICENSE at the repo root).
// GENERATED from src/ by \`npm run build\` (esbuild, one file, no dependencies). Do not edit.`;

/** The bundle as a string, deterministic for the same sources and esbuild version. */
export async function bundle() {
  const result = await build({
    absWorkingDir: ROOT,
    entryPoints: ['src/cli.ts'],
    bundle: true,
    platform: 'node',
    format: 'esm',
    target: 'node20',
    charset: 'utf8',
    legalComments: 'none',
    banner: { js: BANNER },
    write: false,
    logLevel: 'silent',
  });
  return result.outputFiles[0].text;
}

async function run() {
  const text = await bundle();
  if (process.argv.includes('--check')) {
    let current = '';
    try {
      current = readFileSync(OUT, 'utf8');
    } catch {
      /* missing counts as stale */
    }
    if (current !== text) {
      console.error('dist/cli.js is stale: run `npm run build` and commit it');
      process.exit(1);
    }
    console.log('dist/cli.js is up to date');
    return;
  }
  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, text, { mode: 0o755 });
  console.log(`wrote dist/cli.js (${text.length} bytes)`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) await run();
