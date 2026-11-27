import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';
import { parse } from 'yaml';
import { BIN, CLI_DIR, REPO_ROOT, fakeGh, repo, run } from './helpers.mjs';

const VERSION = JSON.parse(readFileSync(join(CLI_DIR, 'package.json'), 'utf8')).version;
const SCHEMA = JSON.parse(readFileSync(join(REPO_ROOT, 'core', 'schema', 'config.schema.json'), 'utf8'));
const { validate } = await import('../src/schema.mjs');
const actionlint = spawnSync('actionlint', ['-version']).status === 0;

test('--version and --help', () => {
  assert.equal(run(['--version']).out, `${VERSION}\n`);
  const help = run(['--help']);
  assert.equal(help.code, 0);
  for (const s of ['init', 'doctor', 'flare', 'FSL-1.1-ALv2']) assert.match(help.out, new RegExp(s));
  assert.match(run(['init', '--help']).out, /--dry-run/);
  assert.match(run(['doctor', '--help']).out, /pinned/);
  assert.equal(run(['nope']).code, 2);
});

test('the bundle is one file with no imports beyond node builtins', () => {
  const text = readFileSync(BIN, 'utf8');
  assert.ok(text.startsWith('#!/usr/bin/env node\n'));
  const imports = [...text.matchAll(/^import .* from ["']([^"']+)["'];?$/gm)].map((m) => m[1]);
  assert.ok(imports.length > 0 && imports.every((m) => m.startsWith('node:')), imports.join(' '));
  assert.doesNotMatch(text, /\/Users\/|\/home\//, 'no local paths in the bundle');
});

test('dawnfix flare runs the bundled Flare CLI', () => {
  const r = run(['flare', '--help']);
  assert.equal(r.code, 0);
  assert.match(r.out, /Dawnfix Flare: read-only audit of Cloudflare/);
  const snap = run(['flare', '--snapshot-in', join(REPO_ROOT, 'flare', 'examples', 'demo-snapshot.json'), '--json', '--no-state', '--fail-on', 'never']);
  assert.equal(snap.code, 0, snap.err);
  assert.ok(JSON.parse(snap.out).findings.length > 0);
});

test('init --dry-run shows both files and the next steps, writes nothing', () => {
  const dir = repo({ 'package.json': '{}', 'package-lock.json': '{}' });
  const r = run(['init', '--dry-run', '--log-group', 'api-prod'], { cwd: dir });
  assert.equal(r.code, 0, r.err);
  assert.match(r.out, /--- \.dawnfix\.yml/);
  assert.match(r.out, /--- \.github\/workflows\/dawnfix\.yml/);
  assert.match(r.out, /gh secret set ANTHROPIC_API_KEY\n/);
  assert.match(r.out, /aws cloudformation deploy --template-file dawnfix-read-role\.yaml/);
  assert.match(r.out, new RegExp(`raw\\.githubusercontent\\.com/dawnfix/dawnfix/v${VERSION.replace(/\./g, '\\.')}/infra/aws/dawnfix-read-role\\.yaml`));
  assert.match(r.out, /GitHubOrg=octo GitHubRepo=shop-api Branch=main/);
  assert.ok(!existsSync(join(dir, '.dawnfix.yml')) && !existsSync(join(dir, '.github')));
});

test('init without a terminal and without --yes writes nothing', () => {
  const dir = repo();
  const r = run(['init', '--log-group', 'a'], { cwd: dir });
  assert.equal(r.code, 2);
  assert.match(r.err, /re-run with --yes/);
  assert.ok(!existsSync(join(dir, '.dawnfix.yml')));
});

test('init --yes writes a valid config and a short pinned caller; no secret anywhere', () => {
  const dir = repo({ 'go.mod': 'module x\n' });
  const r = run(['init', '--yes', '--log-group', 'api-prod', '--autonomy', 'draft-pr',
    '--aws-role-arn', 'arn:aws:iam::123456789012:role/dawnfix-read-shop-api'], { cwd: dir });
  assert.equal(r.code, 0, r.err);
  const cfg = parse(readFileSync(join(dir, '.dawnfix.yml'), 'utf8'));
  assert.deepEqual(validate(SCHEMA, cfg), []);
  assert.equal(cfg.autonomy, 'draft-pr');
  assert.equal(cfg.test.command, 'go test ./...');
  const text = readFileSync(join(dir, '.github', 'workflows', 'dawnfix.yml'), 'utf8');
  assert.ok(text.trim().split('\n').length <= 17, `about 15 lines, got:\n${text}`);
  const wf = parse(text);
  assert.equal(wf.jobs.dawnfix.uses, 'dawnfix/dawnfix/.github/workflows/dawnfix.yml@v0');
  assert.equal(wf.jobs.dawnfix.with['aws-role-arn'], 'arn:aws:iam::123456789012:role/dawnfix-read-shop-api');
  assert.equal(wf.jobs.dawnfix.with['install-command'], 'go mod download');
  assert.deepEqual(wf.permissions, { contents: 'write', 'pull-requests': 'write', issues: 'write', 'id-token': 'write' });
  assert.deepEqual(Object.keys(wf.jobs.dawnfix.secrets), ['ANTHROPIC_API_KEY', 'DAWNFIX_ENTERPRISE_KEY']);
  assert.match(r.out, /wrote \.dawnfix\.yml\nwrote \.github\/workflows\/dawnfix\.yml/);
  assert.doesNotMatch(r.out, /gh variable set DAWNFIX_AWS_ROLE_ARN/, 'the role was given');
  // The files exist now: a second run refuses unless --force.
  const again = run(['init', '--yes', '--log-group', 'x'], { cwd: dir });
  assert.equal(again.code, 2);
  assert.match(again.err, /exist already/);
});

test('init for GCP, and bad flags are named', () => {
  const dir = repo();
  const r = run(['init', '--yes', '--cloud', 'gcp', '--gcp-project', 'my-proj-1'], { cwd: dir });
  assert.equal(r.code, 0, r.err);
  assert.match(readFileSync(join(dir, '.github/workflows/dawnfix.yml'), 'utf8'), /gcp-wif-provider: \$\{\{ vars\.DAWNFIX_GCP_WIF_PROVIDER \}\}/);
  assert.match(r.out, /bash setup-wif\.sh --branch main my-proj-1 octo\/shop-api/);
  for (const [args, msg] of [
    [['--cloud', 'azure'], /--cloud must be aws or gcp/],
    [['--autonomy', 'yolo'], /--autonomy must be/],
    [['--test-command', 'npm test && curl x', '--autonomy', 'draft-pr'], /test\/command/],
    [['--ref', 'main'], /--ref must be a release tag/],
    [['--aws-role-arn', 'admin'], /not an IAM role ARN/],
    [['--cloud', 'gcp'], /--gcp-project is required/],
  ]) {
    const bad = run(['init', '--dry-run', '--log-group', 'a', ...args], { cwd: repo() });
    assert.equal(bad.code, 2, args.join(' '));
    assert.match(bad.err, msg);
  }
  const outside = run(['init', '--dry-run'], { cwd: '/' });
  assert.equal(outside.code, 2);
  assert.match(outside.err, /not inside a git repository/);
});

test('the caller init writes passes actionlint against the reusable workflow', { skip: !actionlint && 'actionlint not installed' }, () => {
  const dir = repo();
  assert.equal(run(['init', '--yes', '--log-group', 'a', '--autonomy', 'plan', '--install-command', 'npm ci', '--enterprise'], { cwd: dir }).code, 0);
  const wfdir = join(dir, '.github', 'workflows');
  // .github/workflows/ in the public repo; public/.github/workflows/ in the one it is cut from.
  const published = join(REPO_ROOT, '.github', 'workflows', 'dawnfix.yml');
  copyFileSync(existsSync(published) ? published : join(REPO_ROOT, 'public', '.github', 'workflows', 'dawnfix.yml'), join(wfdir, 'reusable-dawnfix.yml'));
  const caller = join(wfdir, 'dawnfix.yml');
  writeFileSync(caller, readFileSync(caller, 'utf8').replace(/dawnfix\/dawnfix\/\.github\/workflows\/dawnfix\.yml@v0/, './.github/workflows/reusable-dawnfix.yml'));
  const p = spawnSync('actionlint', ['-no-color'], { cwd: dir, encoding: 'utf8' });
  assert.equal(p.status, 0, p.stdout + p.stderr);
});

test('doctor: a good setup with gh, Free then Enterprise', () => {
  const dir = repo();
  run(['init', '--yes', '--log-group', 'a'], { cwd: dir });
  let gh = fakeGh({ secrets: ['ANTHROPIC_API_KEY'], vars: ['DAWNFIX_AWS_ROLE_ARN'] });
  let r = run(['doctor'], { cwd: dir, path: gh });
  assert.equal(r.code, 0, r.out);
  assert.match(r.out, /ok {4}\.dawnfix\.yml is valid/);
  assert.match(r.out, /calls dawnfix\/dawnfix@v0/);
  assert.match(r.out, /secret ANTHROPIC_API_KEY is set/);
  assert.match(r.out, /variable DAWNFIX_AWS_ROLE_ARN is set/);
  assert.match(r.out, /plan: Free & source available/);
  assert.match(readFileSync(join(gh, 'gh.log'), 'utf8'), /secret list -R octo\/shop-api --json name/);
  gh = fakeGh({ secrets: ['ANTHROPIC_API_KEY', 'DAWNFIX_ENTERPRISE_KEY'], vars: ['DAWNFIX_AWS_ROLE_ARN'] });
  r = run(['doctor'], { cwd: dir, path: gh });
  assert.equal(r.code, 0, r.out);
  assert.match(r.out, /plan: Enterprise/);
});

test('doctor: missing names, an unpinned workflow and a bad config fail', () => {
  const dir = repo();
  run(['init', '--yes', '--log-group', 'a'], { cwd: dir });
  const wf = join(dir, '.github/workflows/dawnfix.yml');
  writeFileSync(wf, readFileSync(wf, 'utf8').replace('@v0', '@main').replace(', id-token: write', ''));
  writeFileSync(join(dir, '.dawnfix.yml'), 'version: 1\nautonomy: yolo\nsources: [{aws: {region: us-east-1}}]\n');
  const r = run(['doctor'], { cwd: dir, path: fakeGh({ secrets: [], vars: [] }) });
  assert.equal(r.code, 1);
  assert.match(r.out, /FAIL {2}\.dawnfix\.yml has 2 problem/);
  assert.match(r.out, /\/autonomy: must be one of diagnose, plan, draft-pr/);
  assert.match(r.out, /\/sources\/0\/aws/);
  assert.match(r.out, /dawnfix\.yml@main: not pinned to a release/);
  assert.match(r.out, /must grant id-token: write/);
  assert.match(r.out, /secret ANTHROPIC_API_KEY is not set: gh secret set ANTHROPIC_API_KEY/);
  assert.match(r.out, /variable DAWNFIX_AWS_ROLE_ARN is not set/);
});

test('doctor without gh lists the names to check, and knows the template form', () => {
  const dir = repo({ '.dawnfix.yml': readFileSync(join(REPO_ROOT, 'templates', 'dawnfix.yml'), 'utf8') });
  mkdirSync(join(dir, '.github', 'workflows'), { recursive: true });
  copyFileSync(join(REPO_ROOT, 'templates', 'github', 'workflows', 'dawnfix.yml'), join(dir, '.github', 'workflows', 'dawnfix.yml'));
  const r = run(['doctor'], { cwd: dir, path: fakeGh({ fail: true }) });
  assert.equal(r.code, 0, r.out);
  assert.match(r.out, new RegExp(`copy-it-yourself template of v${VERSION.replace(/\./g, '\\.')}`));
  assert.match(r.out, /could not list the repo's secrets with gh \(gh: not logged in\)/);
  assert.match(r.out, /secret ANTHROPIC_API_KEY\n/);
  assert.match(r.out, /variable DAWNFIX_AWS_ROLE_ARN\n/);
  const none = run(['doctor'], { cwd: repo() , path: fakeGh() });
  assert.equal(none.code, 1);
  assert.match(none.out, /\.dawnfix\.yml is missing/);
  assert.match(none.out, /no Dawnfix workflow/);
});

test('dist/cli.js is what the sources build to', () => {
  execFileSync(process.execPath, [join(CLI_DIR, 'build.mjs'), '--check'], { stdio: 'pipe' });
});
