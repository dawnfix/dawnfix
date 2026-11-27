// npx dawnfix init --host gitlab: .dawnfix.yml and a .gitlab-ci.yml that includes the release's
// template with GitLab's integrity check; an existing .gitlab-ci.yml is never touched.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, mkdtempSync, readFileSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { parse } from 'yaml';
import { CLI_DIR, REPO_ROOT, gitlabRepo, repo, run } from './helpers.mjs';

const VERSION = JSON.parse(readFileSync(join(CLI_DIR, 'package.json'), 'utf8')).version;
const SCHEMA = JSON.parse(readFileSync(join(REPO_ROOT, 'core', 'schema', 'config.schema.json'), 'utf8'));
const { validate } = await import('../src/schema.mjs');
const { gitlabFromRemote } = await import('../src/repo.mjs');
const TEMPLATE = join(REPO_ROOT, 'templates', 'gitlab', 'dawnfix.gitlab-ci.yml');
const INTEGRITY = `sha256-${createHash('sha256').update(readFileSync(TEMPLATE)).digest('base64')}`;
const URL = `https://raw.githubusercontent.com/dawnfix/dawnfix/v${VERSION}/templates/gitlab/dawnfix.gitlab-ci.yml`;
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&');
const INIT = ['init', '--yes', '--log-group', 'api-prod'];

test('GitLab remotes yield host and full project path; others do not', () => {
  assert.deepEqual(gitlabFromRemote('git@gitlab.com:acme/platform/shop-api.git'), { host: 'gitlab.com', path: 'acme/platform/shop-api' });
  assert.deepEqual(gitlabFromRemote('https://gitlab.com/acme/api'), { host: 'gitlab.com', path: 'acme/api' });
  assert.deepEqual(gitlabFromRemote('ssh://git@gitlab.corp.example:2222/a/b/c.git'), { host: 'gitlab.corp.example', path: 'a/b/c' });
  assert.deepEqual(gitlabFromRemote('https://oauth2:x@gitlab.example.com/g/p.git/'), { host: 'gitlab.example.com', path: 'g/p' });
  for (const u of ['git@github.com:octo/shop-api.git', 'https://bitbucket.org/a/b', '', 'gitlab.com']) assert.equal(gitlabFromRemote(u), null, u);
});

test('init on a GitLab remote writes .dawnfix.yml and .gitlab-ci.yml with the pinned include', () => {
  const dir = gitlabRepo();
  const r = run(INIT, { cwd: dir });
  assert.equal(r.code, 0, r.err);
  assert.match(r.out, /wrote \.dawnfix\.yml\nwrote \.gitlab-ci\.yml/);
  assert.ok(!existsSync(join(dir, '.github')), 'no GitHub workflow');
  const cfg = parse(readFileSync(join(dir, '.dawnfix.yml'), 'utf8'));
  assert.deepEqual(validate(SCHEMA, cfg), []);
  assert.equal(cfg.report.issues, 'host');
  const text = readFileSync(join(dir, '.gitlab-ci.yml'), 'utf8');
  assert.deepEqual(parse(text), { include: [{ remote: URL, integrity: INTEGRITY }] });
  // The header explains the integrity and names the variables to set.
  assert.match(text, /^# .*integrity: GitLab fetches the template/m);
  for (const [v, env] of [['DAWNFIX_AI_API_KEY', 'dawnfix-agent'], ['DAWNFIX_HOST_TOKEN', 'dawnfix-publish'], ['DAWNFIX_ENTERPRISE_KEY', 'dawnfix-report']]) {
    assert.match(text, new RegExp(`^#\\s+${v}\\s+masked, protected, environment ${env}`, 'm'));
  }
  assert.match(text, /^# Not secret: DAWNFIX_AWS_ROLE_ARN, DAWNFIX_AWS_REGION$/m);
});

test('the integrity is the sha256 of the template bytes shipped at this tag', () => {
  const r = run(['init', '--dry-run', '--host', 'gitlab', '--log-group', 'a'], { cwd: gitlabRepo() });
  assert.equal(r.code, 0, r.err);
  assert.match(r.out, new RegExp(`- remote: ${esc(URL)}\\n {4}integrity: ${esc(INTEGRITY)}\\n`));
});

test('the next steps: cloud trust, glab secret lines (value from stdin), token, schedule, manual runs, doctor', () => {
  const r = run(INIT, { cwd: gitlabRepo() });
  assert.equal(r.code, 0, r.err);
  const o = r.out;
  assert.match(o, new RegExp(esc(`curl -fsSLO https://raw.githubusercontent.com/dawnfix/dawnfix/v${VERSION}/infra/aws/dawnfix-read-role-gitlab.yaml`)));
  assert.match(o, /--parameter-overrides ProjectPath=acme\/platform\/shop-api Branch=main \\\n\s+CreateOIDCProvider=true RoleName=dawnfix-read-shop-api LogGroupPrefix='\*'\n/);
  assert.match(o, /glab variable set DAWNFIX_AWS_ROLE_ARN --value "\$\(aws cloudformation describe-stacks --stack-name dawnfix-read-shop-api/);
  assert.match(o, /glab variable set DAWNFIX_AWS_REGION --value us-east-1\n/);
  assert.match(o, /printf %s "\$V" \| glab variable set DAWNFIX_AI_API_KEY --masked --protected --scope dawnfix-agent;/);
  assert.match(o, /\| glab variable set DAWNFIX_HOST_TOKEN --masked --protected --scope dawnfix-publish\n/);
  assert.match(o, /printf %s "\$V" \| glab variable set DAWNFIX_ENTERPRISE_KEY --masked --protected --scope dawnfix-report;/);
  assert.match(o, /glab token create dawnfix --access-level developer --scope api --scope write_repository/);
  assert.match(o, /role Developer, scopes api and write_repository/);
  assert.match(o, /glab schedule create --cron "17 \* \* \* \*" --ref main --description dawnfix --variable "DAWNFIX_RUN:true"/);
  assert.match(o, /glab ci run --branch main --variables DAWNFIX_RUN:true --variables DAWNFIX_DRY_RUN:true/);
  assert.match(o, /glab ci run --branch main --variables DAWNFIX_RUN:true --variables DAWNFIX_BASELINE:true/);
  assert.match(o, /npx dawnfix doctor/);
  assert.doesNotMatch(o, /gh secret set|\.github\/workflows/);
});

test('no secret ever goes on a command line, and init has no secret flags', () => {
  const r = run(INIT, { cwd: gitlabRepo() });
  for (const line of r.out.split('\n').filter((l) => /glab variable set/.test(l))) {
    if (/DAWNFIX_(AI_API_KEY|HOST_TOKEN|ENTERPRISE_KEY)/.test(line)) assert.doesNotMatch(line, /--value|-v /, line);
  }
  const help = run(['init', '--help']).out;
  assert.match(help, /--host github\|gitlab/);
  assert.doesNotMatch(help, /--(ai-api-key|api-key|token|host-token|enterprise-key|secret)\b/);
  const bad = run([...INIT, '--host-token', 'glpat-xyz'], { cwd: gitlabRepo() });
  assert.equal(bad.code, 2);
});

test('GCP and a self-managed GitLab: setup-wif-gitlab.sh with --gitlab-url', () => {
  const dir = gitlabRepo({}, 'https://gitlab.corp.example/team/svc.git');
  const r = run(['init', '--yes', '--cloud', 'gcp', '--gcp-project', 'my-proj-1'], { cwd: dir });
  assert.equal(r.code, 0, r.err);
  assert.match(r.out, /curl -fsSLO \S+\/infra\/gcp\/setup-wif-gitlab\.sh/);
  assert.match(r.out, /bash setup-wif-gitlab\.sh --branch main --gitlab-url https:\/\/gitlab\.corp\.example my-proj-1 team\/svc\n/);
  assert.match(r.out, /glab variable set DAWNFIX_GCP_WIF_PROVIDER --value/);
  assert.match(readFileSync(join(dir, '.gitlab-ci.yml'), 'utf8'), /^# Not secret: DAWNFIX_GCP_WIF_PROVIDER$/m);
  const aws = run(['init', '--dry-run', '--log-group', 'a'], { cwd: gitlabRepo({}, 'git@gitlab.corp.example:team/svc.git') });
  assert.match(aws.out, /LogGroupPrefix='\*' GitLabUrl=https:\/\/gitlab\.corp\.example\n/);
});

test('an existing .gitlab-ci.yml is never modified, even with --force; the snippet is printed', () => {
  const existing = 'stages: [test]\nunit:\n  script: [make test]\n';
  const dir = gitlabRepo({ '.gitlab-ci.yml': existing });
  const r = run([...INIT, '--force'], { cwd: dir });
  assert.equal(r.code, 0, r.err);
  assert.equal(readFileSync(join(dir, '.gitlab-ci.yml'), 'utf8'), existing);
  assert.ok(existsSync(join(dir, '.dawnfix.yml')));
  assert.match(r.out, /wrote \.dawnfix\.yml\n/);
  assert.doesNotMatch(r.out, /wrote \.gitlab-ci\.yml/);
  assert.match(r.out, /\.gitlab-ci\.yml exists, so dawnfix does not change it \(not even with --force\)/);
  assert.match(r.out, new RegExp(`include:\\n  - remote: ${esc(URL)}\\n    integrity: ${esc(INTEGRITY)}\\n`));
  assert.match(r.out, /Add the include to \.gitlab-ci\.yml/);
});

test('an existing .gitlab-ci.yml that already includes Dawnfix is recognised', () => {
  const existing = `include:\n  - remote: ${URL.replace(`v${VERSION}`, 'v0.3.0')}\n    integrity: sha256-old\n`;
  const dir = gitlabRepo({ '.gitlab-ci.yml': existing });
  const r = run(INIT, { cwd: dir });
  assert.equal(r.code, 0, r.err);
  assert.equal(readFileSync(join(dir, '.gitlab-ci.yml'), 'utf8'), existing);
  assert.match(r.out, /already includes the Dawnfix template/);
  assert.match(r.out, new RegExp(`To move it to v${esc(VERSION)}, replace that include with these lines`));
});

test('a symlinked .gitlab-ci.yml is refused and nothing is written', () => {
  const dir = gitlabRepo();
  const outside = mkdtempSync(join(tmpdir(), 'dawnfix-outside-'));
  writeFileSync(join(outside, 'victim.yml'), 'keep me\n');
  symlinkSync(join(outside, 'victim.yml'), join(dir, '.gitlab-ci.yml'));
  for (const args of [INIT, [...INIT, '--force']]) {
    const r = run(args, { cwd: dir });
    assert.equal(r.code, 2);
    assert.match(r.err, /\.gitlab-ci\.yml is a symbolic link/);
  }
  assert.equal(readFileSync(join(outside, 'victim.yml'), 'utf8'), 'keep me\n');
  assert.ok(!existsSync(join(dir, '.dawnfix.yml')));
});

test('--host: bad values, GitHub-only flags, and GitHub stays the default for a GitHub remote', () => {
  const bad = run(['init', '--dry-run', '--host', 'circleci', '--log-group', 'a'], { cwd: repo() });
  assert.equal(bad.code, 2);
  assert.match(bad.err, /--host must be github or gitlab/);
  // Bitbucket is not in this release: a plain "coming soon", non-zero, nothing written.
  const bbDir = repo();
  const bb = run(['init', '--host', 'bitbucket', '--log-group', 'a'], { cwd: bbDir });
  assert.notEqual(bb.code, 0);
  assert.match(bb.err, /Bitbucket support is coming soon/);
  assert.doesNotMatch(bb.out, /bitbucket-pipelines/);
  assert.ok(!existsSync(join(bbDir, '.dawnfix.yml')));
  assert.match(run(['init', '--dry-run', '--log-group', 'a', '--ref', 'v0'], { cwd: gitlabRepo() }).err, /--ref is for GitHub/);
  const gh = run(['init', '--dry-run', '--log-group', 'a'], { cwd: repo() });
  assert.match(gh.out, /--- \.github\/workflows\/dawnfix\.yml/);
  assert.doesNotMatch(gh.out, /gitlab/i);
  assert.match(gh.out, /  issues: github\n/);
  // --host gitlab on a GitHub remote: the GitLab files, GROUP/PROJECT placeholders.
  const forced = run(['init', '--dry-run', '--host', 'gitlab', '--log-group', 'a'], { cwd: repo() });
  assert.equal(forced.code, 0, forced.err);
  assert.match(forced.out, /--- \.gitlab-ci\.yml/);
  assert.match(forced.out, /ProjectPath=GROUP\/PROJECT/);
  // --host github on a GitLab remote: the GitHub files.
  const back = run(['init', '--dry-run', '--host', 'github', '--log-group', 'a'], { cwd: gitlabRepo() });
  assert.match(back.out, /--- \.github\/workflows\/dawnfix\.yml/);
});

test('doctor accepts a GitLab setup and lists the CI/CD variables to check', () => {
  const dir = gitlabRepo();
  assert.equal(run(INIT, { cwd: dir }).code, 0);
  const r = run(['doctor'], { cwd: dir });
  assert.equal(r.code, 0, r.out);
  assert.match(r.out, new RegExp(`ok {4}\\.gitlab-ci\\.yml includes the Dawnfix template of v${esc(VERSION)}, pinned with its integrity`));
  assert.match(r.out, /secret DAWNFIX_HOST_TOKEN \(masked, protected, environment dawnfix-publish\)/);
  assert.match(r.out, /variable DAWNFIX_AWS_ROLE_ARN/);
  assert.doesNotMatch(r.out, /no Dawnfix workflow/);
  // A tampered hash fails; jobs defined by hand pass.
  const ci = join(dir, '.gitlab-ci.yml');
  writeFileSync(ci, readFileSync(ci, 'utf8').replace(/integrity: \S+/, 'integrity: sha256-AAAA'));
  assert.equal(run(['doctor'], { cwd: dir }).code, 1);
  writeFileSync(ci, 'dawnfix-read:\n  script: [true]\n');
  assert.match(run(['doctor'], { cwd: dir }).out, /defines the Dawnfix jobs/);
  writeFileSync(ci, 'unit:\n  script: [true]\n');
  const none = run(['doctor'], { cwd: dir });
  assert.equal(none.code, 1);
  assert.match(none.out, /no Dawnfix include in \.gitlab-ci\.yml/);
});
