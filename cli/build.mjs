// Bundles src/cli.mjs and everything it imports (Flare's sources, the .dawnfix.yml schema
// from core/schema/, the GitLab template from templates/gitlab/ as its exact bytes, the yaml
// parser) into one file, dist/cli.js, with no runtime dependency:
// `npx dawnfix` runs it with plain node 20 or newer. dist/cli.js is checked in.
//
//   node build.mjs            write dist/cli.js
//   node build.mjs --check    exit 1 if dist/cli.js is stale (test/build.test.mjs does the same)
import { build } from 'esbuild';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = dirname(fileURLToPath(import.meta.url));
export const OUT = join(ROOT, 'dist', 'cli.js');
const VERSION = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8')).version;

const BANNER = `#!/usr/bin/env node
// Dawnfix ${VERSION}: npx dawnfix init | doctor | flare.
// Source available under FSL-1.1-ALv2 (see LICENSE in this package).
// GENERATED from cli/src/ and flare/src/ by \`npm run build\` (esbuild, one file, no dependencies). Do not edit.
import { createRequire as __dawnfixRequire } from 'node:module';
const require = __dawnfixRequire(import.meta.url);`;

/** The bundle as a string, deterministic for the same sources and esbuild version. */
export async function bundle() {
  const result = await build({
    absWorkingDir: ROOT,
    entryPoints: ['src/cli.mjs'],
    bundle: true,
    platform: 'node',
    format: 'esm',
    target: 'node20',
    charset: 'utf8',
    legalComments: 'none',
    banner: { js: BANNER },
    define: { __DAWNFIX_VERSION__: JSON.stringify(VERSION) },
    // templates/gitlab/dawnfix.gitlab-ci.yml, byte for byte: init hashes it for `integrity:`.
    loader: { '.yml': 'binary' },
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
      console.error('cli/dist/cli.js is stale: run `npm run build` in cli/ and commit it');
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
