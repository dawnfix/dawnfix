// npx dawnfix init --host bitbucket: .dawnfix.yml and bitbucket-pipelines.yml (the release's
// template, byte for byte); an existing bitbucket-pipelines.yml is never touched.
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readFileSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { parse } from 'yaml';
import { bitbucketRepo, CLI_DIR, REPO_ROOT, repo, run } from './helpers.mjs';

const VERSION = JSON.parse(readFileSync(join(CLI_DIR, 'package.json'), 'utf8')).version;
const SCHEMA = JSON.parse(readFileSync(join(REPO_ROOT, 'core', 'schema', 'config.schema.json'), 'utf8'));
const { validate } = await import('../src/schema.mjs');
const { bitbucketFromRemote, gitlabFromRemote } = await import('../src/repo.mjs');
const TEMPLATE = readFileSync(join(REPO_ROOT, 'templates', 'bitbucket', 'bitbucket-pipelines.yml'), 'utf8');
const SNIPPET = TEMPLATE.slice(TEMPLATE.search(/^definitions:/m));
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&');
const INIT = ['init', '--yes', '--log-group', 'api-prod'];
const FILE = 'bitbucket-pipelines.yml';

test('bitbucket.org remotes yield workspace and repo; others do not', () => {
  assert.deepEqual(bitbucketFromRemote('git@bitbucket.org:acme/shop-api.git'), { workspace: 'acme', slug: 'shop-api' });
  assert.deepEqual(bitbucketFromRemote('https://bitbucket.org/acme/shop-api'), { workspace: 'acme', slug: 'shop-api' });
  assert.deepEqual(bitbucketFromRemote('https://someone@bitbucket.org/acme/shop.api.git/'), { workspace: 'acme', slug: 'shop.api' });
  assert.deepEqual(bitbucketFromRemote('ssh://git@bitbucket.org/acme/x.git'), { workspace: 'acme', slug: 'x' });
  for (const u of ['git@github.com:octo/a.git', 'https://gitlab.com/a/b', 'https://bitbucket.org/a/b/c', 'https://bitbucket.org.evil.example/a/b', '']) {
    assert.equal(bitbucketFromRemote(u), null, u);
  }
  assert.equal(gitlabFromRemote('https://bitbucket.org/a/b'), null);
});

test('init on a Bitbucket remote writes .dawnfix.yml and the template as bitbucket-pipelines.yml', () => {
  const dir = bitbucketRepo();
  const r = run(INIT, { cwd: dir });
  assert.equal(r.code, 0, r.err);
  assert.match(r.out, /^Dawnfix .* in acme\/shop-api\./);
  assert.match(r.out, /wrote \.dawnfix\.yml\nwrote bitbucket-pipelines\.yml/);
  assert.ok(!existsSync(join(dir, '.github')) && !existsSync(join(dir, '.gitlab-ci.yml')));
  const cfg = parse(readFileSync(join(dir, '.dawnfix.yml'), 'utf8'));
  assert.deepEqual(validate(SCHEMA, cfg), []);
  assert.equal(cfg.report.issues, 'host');
  assert.match(readFileSync(join(dir, '.dawnfix.yml'), 'utf8'), /Bitbucket pipeline schedule \(custom: dawnfix\)/);
  const text = readFileSync(join(dir, FILE), 'utf8');
  assert.equal(text, TEMPLATE, 'the template, byte for byte');
  assert.match(text, new RegExp(`export DAWNFIX_VERSION="${esc(VERSION)}"`));
  assert.ok(parse(text).pipelines.custom.dawnfix.length >= 4);
});

test('the next steps: UUIDs, cloud trust, Pipelines, environments, secured deployment variables, schedule, first run', () => {
  const r = run(INIT, { cwd: bitbucketRepo() });
  assert.equal(r.code, 0, r.err);
  const o = r.out;
  assert.match(o, /Repository settings > Pipelines > OpenID Connect/);
  assert.match(o, /GET https:\/\/api\.bitbucket\.org\/2\.0\/repositories\/acme\/shop-api/);
  assert.match(o, new RegExp(esc(`curl -fsSLO https://raw.githubusercontent.com/dawnfix/dawnfix/v${VERSION}/infra/aws/dawnfix-read-role-bitbucket.yaml`)));
  assert.match(o, /--parameter-overrides Workspace=acme WorkspaceUuid=<workspace UUID, no braces> \\\n\s+RepositoryUuid='\{<repository UUID>\}' CreateOIDCProvider=true RoleName=dawnfix-read-shop-api LogGroupPrefix='\*'\n/);
  assert.match(o, /DAWNFIX_AWS_REGION = us-east-1\n/);
  assert.match(o, /Enable Pipelines/);
  assert.match(o, /dawnfix-agent\s+type Test\n\s+dawnfix-publish\s+type Staging\n\s+dawnfix-report\s+type Production\n/);
  assert.match(o, /DAWNFIX_AI_API_KEY\s+in dawnfix-agent/);
  assert.match(o, /DAWNFIX_HOST_TOKEN\s+in dawnfix-publish\s+a repository access token: scopes repository:write, pullrequest:write, pipeline:write/);
  assert.match(o, /DAWNFIX_ENTERPRISE_KEY\s+in dawnfix-report\s+optional/);
  assert.match(o, /DAWNFIX_BITBUCKET_EMAIL/);
  assert.match(o, /Never put a secret in repository or workspace variables/);
  assert.match(o, /"cron_pattern":"0 17 \* \* \* \? \*"/);
  assert.match(o, /"selector":\{"type":"custom","pattern":"dawnfix"\}/);
  assert.match(o, /DAWNFIX_BASELINE=true/);
  assert.match(o, /Run pipeline > branch main, custom: dawnfix/);
  assert.match(o, /npx dawnfix doctor/);
  assert.doesNotMatch(o, /gh secret set|glab|\.github\/workflows/);
});

test('no secret value anywhere: the schedule call reads the token from the environment', () => {
  const r = run(INIT, { cwd: bitbucketRepo() });
  const curl = r.out.split('\n').find((l) => /curl -sS -X POST/.test(l));
  assert.match(curl, /Authorization: Bearer \$BITBUCKET_TOKEN/);
  assert.doesNotMatch(r.out, /AT(ATT|CTT|BB)[A-Za-z0-9]{10}|sk-ant-/);
  const bad = run([...INIT, '--host-token', 'x'], { cwd: bitbucketRepo() });
  assert.equal(bad.code, 2);
});

test('GCP: setup-wif-bitbucket.sh and the WIF provider variable', () => {
  const dir = bitbucketRepo({}, 'https://bitbucket.org/team/svc.git');
  const r = run(['init', '--yes', '--cloud', 'gcp', '--gcp-project', 'my-proj-1'], { cwd: dir });
  assert.equal(r.code, 0, r.err);
  assert.match(r.out, /curl -fsSLO \S+\/infra\/gcp\/setup-wif-bitbucket\.sh/);
  assert.match(r.out, /bash setup-wif-bitbucket\.sh --branch main team <workspace UUID> '\{<repository UUID>\}' my-proj-1\n/);
  assert.match(r.out, /DAWNFIX_GCP_WIF_PROVIDER = /);
});

test('an existing bitbucket-pipelines.yml is never modified, even with --force; the part to merge is printed', () => {
  const existing = 'pipelines:\n  default:\n    - step:\n        script: [make test]\n';
  const dir = bitbucketRepo({ [FILE]: existing });
  const r = run([...INIT, '--force'], { cwd: dir });
  assert.equal(r.code, 0, r.err);
  assert.equal(readFileSync(join(dir, FILE), 'utf8'), existing);
  assert.ok(existsSync(join(dir, '.dawnfix.yml')));
  assert.doesNotMatch(r.out, /wrote bitbucket-pipelines\.yml/);
  assert.match(r.out, /bitbucket-pipelines\.yml exists, so dawnfix does not change it \(not even with --force\)/);
  assert.ok(r.out.includes(SNIPPET), 'the definitions and the custom pipeline');
  assert.match(r.out, /Merge the Dawnfix part into bitbucket-pipelines\.yml/);
});

test('an existing bitbucket-pipelines.yml that already has Dawnfix is recognised', () => {
  const dir = bitbucketRepo({ [FILE]: TEMPLATE.replace(/DAWNFIX_VERSION="[^"]+"/, 'DAWNFIX_VERSION="0.3.0"') });
  const r = run(INIT, { cwd: dir });
  assert.equal(r.code, 0, r.err);
  assert.match(r.out, /already defines the Dawnfix pipeline/);
  assert.match(r.out, new RegExp(`To move it to v${esc(VERSION)}`));
});

test('a symlinked bitbucket-pipelines.yml is refused and nothing is written', () => {
  const dir = bitbucketRepo();
  const outside = mkdtempSync(join(tmpdir(), 'dawnfix-outside-'));
  writeFileSync(join(outside, 'victim.yml'), 'keep me\n');
  symlinkSync(join(outside, 'victim.yml'), join(dir, FILE));
  for (const args of [INIT, [...INIT, '--force']]) {
    const r = run(args, { cwd: dir });
    assert.equal(r.code, 2);
    assert.match(r.err, /bitbucket-pipelines\.yml is a symbolic link/);
  }
  assert.equal(readFileSync(join(outside, 'victim.yml'), 'utf8'), 'keep me\n');
  assert.ok(!existsSync(join(dir, '.dawnfix.yml')));
});

test('--host bitbucket: GitHub-only flags refused, placeholders without a bitbucket remote, help', () => {
  assert.match(run(['init', '--dry-run', '--log-group', 'a', '--ref', 'v0'], { cwd: bitbucketRepo() }).err, /--ref is for GitHub; on Bitbucket/);
  assert.match(run(['init', '--dry-run', '--log-group', 'a', '--enterprise'], { cwd: bitbucketRepo() }).err, /--enterprise .* on Bitbucket/);
  const forced = run(['init', '--dry-run', '--host', 'bitbucket', '--log-group', 'a'], { cwd: repo() });
  assert.equal(forced.code, 0, forced.err);
  assert.match(forced.err, /no bitbucket\.org remote/);
  assert.match(forced.out, /--- bitbucket-pipelines\.yml/);
  assert.match(forced.out, /Workspace=WORKSPACE/);
  const help = run(['init', '--help']).out;
  assert.match(help, /--host github\|gitlab\|bitbucket/);
  assert.match(help, /An existing\nbitbucket-pipelines\.yml is never changed/);
  assert.match(run(['--help']).out, /Bitbucket Pipelines/);
});

test('doctor accepts a Bitbucket setup and lists the deployment variables to check', () => {
  const dir = bitbucketRepo();
  assert.equal(run(INIT, { cwd: dir }).code, 0);
  const r = run(['doctor'], { cwd: dir });
  // The one failure: the required push restriction, unchecked without BITBUCKET_TOKEN.
  assert.deepEqual(r.out.split('\n').filter((l) => l.startsWith('FAIL')).map((l) => l.slice(0, 40)),
    ['FAIL  Bitbucket: a push restriction on *']);
  assert.match(r.out, /Dawnfix doctor .*: acme\/shop-api/);
  assert.match(r.out, new RegExp(`ok {4}bitbucket-pipelines\\.yml has the Dawnfix custom pipeline of v${esc(VERSION)}`));
  assert.match(r.out, /secret DAWNFIX_HOST_TOKEN \(secured, deployment environment dawnfix-publish, type Staging\)/);
  assert.match(r.out, /repository variable DAWNFIX_AWS_ROLE_ARN/);
  assert.doesNotMatch(r.out, /no Dawnfix workflow/);
  const f = join(dir, FILE);
  writeFileSync(f, readFileSync(f, 'utf8').replace(/DAWNFIX_VERSION="[^"]+"/, 'DAWNFIX_VERSION="0.3.0"'));
  assert.match(run(['doctor'], { cwd: dir }).out, /runs Dawnfix 0\.3\.0/);
  writeFileSync(f, readFileSync(f, 'utf8').replace('oidc: false', 'oidc: true'));
  assert.match(run(['doctor'], { cwd: dir }).out, /FAIL  bitbucket-pipelines\.yml: oidc: true on more than one step/);
  writeFileSync(f, 'pipelines:\n  default:\n    - step:\n        script: [true]\n');
  const none = run(['doctor'], { cwd: dir });
  assert.equal(none.code, 1);
  assert.match(none.out, /no Dawnfix pipeline in bitbucket-pipelines\.yml/);
});


test('init prints the push restriction on * as REQUIRED, and doctor judges one', async () => {
  const dir = bitbucketRepo();
  const o = run([...INIT, '--dry-run'], { cwd: dir }).out;
  assert.match(o, /REQUIRED: a push restriction on every branch/);
  assert.match(o, /repositories\/acme\/shop-api\/branch-restrictions/);
  assert.match(o, /"kind":"push","branch_match_kind":"glob","pattern":"\*"/);
  assert.doesNotMatch(o, /BITBUCKET_TOKEN=/);
  const { pushRestrictionVerdict } = await import('../src/bitbucket-check.mjs');
  assert.equal(pushRestrictionVerdict([]).ok, false);
  assert.equal(pushRestrictionVerdict([{ kind: 'push', pattern: 'main', users: [{ uuid: '{u}' }] }]).ok, false);
  assert.equal(pushRestrictionVerdict([{ kind: 'force', pattern: '*' }]).ok, false);
  const v = pushRestrictionVerdict([{ kind: 'push', pattern: '*', branch_match_kind: 'glob', users: [{ display_name: 'dawnfix bot' }], groups: [] }]);
  assert.equal(v.ok, true);
  assert.match(v.why, /only dawnfix bot/);
});


test('on Bitbucket init writes diagnose and says why; fix modes need --self-hosted-runner', () => {
  const dir = bitbucketRepo();
  const r = run(INIT, { cwd: dir });
  assert.equal(r.code, 0, r.err);
  assert.match(readFileSync(join(dir, '.dawnfix.yml'), 'utf8'), /^autonomy: diagnose$/m);
  assert.match(r.err, /diagnose mode only/);
  const refused = run([...INIT, '--autonomy', 'draft-pr', '--test-command', 'npm test'], { cwd: bitbucketRepo() });
  assert.notEqual(refused.code, 0);
  assert.match(refused.err, /self-hosted runner/);
  assert.match(refused.err, /bwrap can create user and network namespaces/);
  const dir2 = bitbucketRepo();
  const ok = run([...INIT, '--autonomy', 'draft-pr', '--test-command', 'npm test', '--self-hosted-runner'], { cwd: dir2 });
  assert.equal(ok.code, 0, ok.err);
  assert.match(readFileSync(join(dir2, '.dawnfix.yml'), 'utf8'), /^autonomy: draft-pr$/m);
});

test('doctor fails on Bitbucket when the required push restriction cannot be checked', () => {
  const dir = bitbucketRepo();
  run(INIT, { cwd: dir });
  const r = run(['doctor'], { cwd: dir });
  assert.equal(r.code, 1);
  assert.match(r.out, /FAIL  Bitbucket: a push restriction on \* letting only the publish account push is REQUIRED/);
});
