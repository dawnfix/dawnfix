// init never writes through a symlink or outside the repo.
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { checkTarget, safeWrite, UnsafePath } from '../src/safe-write.mjs';
import { repo, run } from './helpers.mjs';

const INIT = ['init', '--yes', '--log-group', 'a'];

test('a symlinked .github is refused and nothing is written outside', () => {
  const dir = repo();
  const outside = mkdtempSync(join(tmpdir(), 'dawnfix-outside-'));
  symlinkSync(outside, join(dir, '.github'));
  const r = run(INIT, { cwd: dir });
  assert.equal(r.code, 2);
  assert.match(r.err, /\.github is a symbolic link/);
  assert.deepEqual(readdirSync(outside), []);
  assert.ok(!existsSync(join(dir, '.dawnfix.yml')), 'nothing written at all');
});

test('a symlinked workflow file is refused, even with --force', () => {
  const dir = repo();
  const outside = mkdtempSync(join(tmpdir(), 'dawnfix-outside-'));
  writeFileSync(join(outside, 'victim.yml'), 'keep me\n');
  mkdirSync(join(dir, '.github', 'workflows'), { recursive: true });
  symlinkSync(join(outside, 'victim.yml'), join(dir, '.github', 'workflows', 'dawnfix.yml'));
  const r = run([...INIT, '--force'], { cwd: dir });
  assert.equal(r.code, 2);
  assert.match(r.err, /\.github\/workflows\/dawnfix\.yml is a symbolic link/);
  assert.equal(readFileSync(join(outside, 'victim.yml'), 'utf8'), 'keep me\n');
});

test('a dangling symlink is refused too', () => {
  const dir = repo();
  const target = join(mkdtempSync(join(tmpdir(), 'dawnfix-outside-')), 'not-yet.yml');
  symlinkSync(target, join(dir, '.dawnfix.yml'));
  const r = run(INIT, { cwd: dir });
  assert.equal(r.code, 2);
  assert.match(r.err, /\.dawnfix\.yml is a symbolic link/);
  assert.ok(!existsSync(target));
});

test('the normal path works, and --force overwrites a regular file in place', () => {
  const dir = repo();
  assert.equal(run(INIT, { cwd: dir }).code, 0);
  assert.match(readFileSync(join(dir, '.github', 'workflows', 'dawnfix.yml'), 'utf8'), /uses: dawnfix\/dawnfix/);
  assert.equal(run([...INIT, '--force', '--autonomy', 'plan'], { cwd: dir }).code, 0);
  assert.match(readFileSync(join(dir, '.dawnfix.yml'), 'utf8'), /autonomy: plan/);
});

test('paths with .. or absolute paths are refused', () => {
  const dir = repo();
  for (const p of ['../x.yml', '/etc/x.yml', '.github/../../x.yml']) {
    assert.throws(() => checkTarget(dir, p), UnsafePath, p);
    assert.throws(() => safeWrite(dir, p, 'x'), UnsafePath, p);
  }
  safeWrite(dir, 'a/b/c.yml', 'ok\n');
  assert.throws(() => safeWrite(dir, 'a/b/c.yml', 'again\n'), /exists already/);
  assert.equal(readFileSync(join(dir, 'a/b/c.yml'), 'utf8'), 'ok\n');
});
