// The package as npm publishes it: `npm pack`, then install the tarball into an empty project
// in a temp dir (no network: the package has no dependencies) and run it from there.
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { CLI_DIR, REPO_ROOT, repo } from './helpers.mjs';

const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';

test('npm pack: one bundle, the full licence, README; runs from the tarball', () => {
  const out = mkdtempSync(join(tmpdir(), 'dawnfix-pack-'));
  const json = execFileSync(npm, ['pack', '--json', '--pack-destination', out], { cwd: CLI_DIR, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  const [info] = JSON.parse(json.slice(json.indexOf('[')));
  assert.deepEqual(info.files.map((f) => f.path).sort(), ['LICENSE', 'README.md', 'dist/cli.js', 'package.json']);
  assert.equal(info.name, 'dawnfix');
  assert.ok(!existsSync(join(CLI_DIR, 'LICENSE')), 'postpack removed the copied LICENSE');

  const app = mkdtempSync(join(tmpdir(), 'dawnfix-app-'));
  writeFileSync(join(app, 'package.json'), '{"name":"app","private":true}');
  execFileSync(npm, ['install', '--no-audit', '--no-fund', '--offline', join(out, info.filename)], { cwd: app, stdio: 'pipe' });
  const pkg = join(app, 'node_modules', 'dawnfix');
  assert.equal(readFileSync(join(pkg, 'LICENSE'), 'utf8'), readFileSync(join(REPO_ROOT, 'LICENSE'), 'utf8'));
  assert.match(readFileSync(join(pkg, 'LICENSE'), 'utf8'), /^# Functional Source License, Version 1\.1, ALv2 Future License$/m);
  const manifest = JSON.parse(readFileSync(join(pkg, 'package.json'), 'utf8'));
  assert.equal(manifest.license, 'FSL-1.1-ALv2');
  assert.ok(!manifest.dependencies, 'no runtime dependencies');
  const bin = join(app, 'node_modules', '.bin', 'dawnfix');
  assert.equal(execFileSync(bin, ['--version'], { encoding: 'utf8' }).trim(), manifest.version);
  assert.match(execFileSync(bin, ['--help'], { encoding: 'utf8' }), /npx dawnfix <command>/);
  const dir = repo();
  const r = spawnSync(bin, ['init', '--dry-run', '--log-group', 'a'], { cwd: dir, encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /uses: dawnfix\/dawnfix\/\.github\/workflows\/dawnfix\.yml@v0/);
});

test('npm publish --dry-run: npm corrects and drops nothing in package.json (a "./" bin path is silently removed)', () => {
  const manifest = JSON.parse(readFileSync(join(CLI_DIR, 'package.json'), 'utf8'));
  for (const [name, path] of Object.entries(manifest.bin)) {
    assert.doesNotMatch(path, /^\.\//, `bin.${name} must not start with ./`);
    assert.ok(existsSync(join(CLI_DIR, path)), `bin.${name} points at ${path}, which exists`);
  }
  const r = spawnSync(npm, ['publish', '--dry-run', '--ignore-scripts', '--json'], { cwd: CLI_DIR, encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  const log = `${r.stdout}\n${r.stderr}`;
  assert.doesNotMatch(log, /auto-corrected|invalid and removed|errors corrected/i, log);
  const parsed = JSON.parse(r.stdout.slice(r.stdout.indexOf('{')));
  const info = parsed[manifest.name] ?? parsed;
  assert.ok(info.files.some((f) => f.path === 'dist/cli.js'), 'the bin file is in the tarball');
});
