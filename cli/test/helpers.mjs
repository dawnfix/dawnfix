import { execFileSync, spawnSync } from 'node:child_process';
import { chmodSync, mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const CLI_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');
export const REPO_ROOT = join(CLI_DIR, '..');
export const BIN = join(CLI_DIR, 'dist', 'cli.js');

/** A fresh git repo with a GitHub origin and the given files. */
export function repo(files = {}, slug = 'octo/shop-api') {
  const dir = mkdtempSync(join(tmpdir(), 'dawnfix-cli-'));
  execFileSync('git', ['init', '-q', '-b', 'main'], { cwd: dir });
  execFileSync('git', ['remote', 'add', 'origin', `git@github.com:${slug}.git`], { cwd: dir });
  for (const [p, text] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, p)), { recursive: true });
    writeFileSync(join(dir, p), text);
  }
  return dir;
}

/** A directory with a fake `gh` that answers secret/variable lists from env and logs argv. */
export function fakeGh({ secrets = [], vars = [], fail = false } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'dawnfix-gh-'));
  const gh = join(dir, 'gh');
  writeFileSync(gh, `#!/bin/sh
echo "$*" >> "${dir}/gh.log"
${fail ? 'echo "gh: not logged in" >&2; exit 4' : ''}
case "$1" in
  secret) echo '${JSON.stringify(secrets.map((name) => ({ name })))}' ;;
  variable) echo '${JSON.stringify(vars.map((name) => ({ name })))}' ;;
esac
`);
  chmodSync(gh, 0o755);
  return dir;
}

export function run(args, { cwd, path, input } = {}) {
  const env = { ...process.env, NO_COLOR: '1' };
  if (path) env.PATH = `${path}:${process.env.PATH}`;
  const p = spawnSync(process.execPath, [BIN, ...args], { cwd, env, encoding: 'utf8', input: input ?? '' });
  return { code: p.status, out: p.stdout, err: p.stderr };
}
