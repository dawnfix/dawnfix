// npx dawnfix doctor: checks .dawnfix.yml against core's schema, that the workflow calls a
// pinned release, and that the secret and variable names it needs exist (with gh when it is
// installed and signed in; otherwise it lists them for you to check). Reads names only,
// never a secret's value. Exit 0 when nothing failed, 1 otherwise.
import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import { parse as parseYaml } from 'yaml';
import CONFIG_SCHEMA from '../../core/schema/config.schema.json';
import { pushRestrictionVerdict } from './bitbucket-check.mjs';
import { hasDawnfix as bbHasDawnfix, SECRETS as BITBUCKET_SECRETS, versionOf as bbVersionOf } from './bitbucket.mjs';
import { hasDawnfix, INTEGRITY, SECRETS as GITLAB_SECRETS } from './gitlab.mjs';
import { detectRepo } from './repo.mjs';
import { validate } from './schema.mjs';
import { VERSION } from './version.mjs';

export const DOCTOR_HELP = `Usage: dawnfix doctor [--dir DIR] [--no-gh]

Checks the Dawnfix setup of the repo you are in:
  - .dawnfix.yml is valid (core's schema)
  - .github/workflows/ calls dawnfix/dawnfix/.github/workflows/dawnfix.yml at a pinned
    release (a tag such as v0 or v${VERSION}, or a commit SHA), or holds the copy-it-yourself
    template, with the permissions its jobs need and the cron of .dawnfix.yml;
    on GitLab, .gitlab-ci.yml includes the Dawnfix template (pinned, with integrity);
    on Bitbucket, bitbucket-pipelines.yml has the Dawnfix custom pipeline
  - the secrets and variables it uses exist (names only, through gh; --no-gh lists them)
  - Free or Enterprise: whether an Enterprise key is set
Exit 0 when nothing failed, 1 otherwise.
`;

const NEEDED_PERMISSIONS = { contents: 'write', 'pull-requests': 'write', issues: 'write', 'id-token': 'write' };
const USES = /^dawnfix\/dawnfix\/\.github\/workflows\/dawnfix\.yml(?:@(.*))?$/;
const ENTERPRISE = ['DAWNFIX_ENTERPRISE_KEY'];
// Your AI API key (Claude today). The old secret name is read as a fallback for one release.
const AI_SECRET = 'DAWNFIX_AI_API_KEY';
const FALLBACK_AI_SECRET = 'ANTHROPIC_API_KEY'; // deprecated fallback for DAWNFIX_AI_API_KEY

function readYaml(path) {
  return parseYaml(readFileSync(path, 'utf8'));
}

/** The Dawnfix workflow in .github/workflows: { file, doc, kind: 'caller'|'template', job?, ref? }. */
export function findWorkflow(root) {
  const dir = join(root, '.github', 'workflows');
  if (!existsSync(dir)) return null;
  for (const f of readdirSync(dir).filter((n) => /\.ya?ml$/.test(n)).sort()) {
    let doc;
    try {
      doc = readYaml(join(dir, f));
    } catch {
      continue;
    }
    for (const [name, job] of Object.entries(doc?.jobs || {})) {
      const m = USES.exec(String(job?.uses || ''));
      if (m) return { file: `.github/workflows/${f}`, doc, kind: 'caller', job: name, jobDoc: job, ref: m[1] || '' };
    }
    if (doc?.env?.DAWNFIX_VERSION && doc?.jobs?.read && doc?.jobs?.['pr-state']) {
      return { file: `.github/workflows/${f}`, doc, kind: 'template', ref: `v${doc.env.DAWNFIX_VERSION}` };
    }
  }
  return null;
}

export function pinned(ref) {
  if (/^[0-9a-f]{40}$/.test(ref)) return 'sha';
  if (/^v\d+\.\d+\.\d+$/.test(ref)) return 'release';
  if (/^v\d+(\.\d+)?$/.test(ref)) return 'major';
  return '';
}

/** Names in `${{ secrets.X }}` and `${{ vars.X }}` expressions of a text. */
export function referenced(text) {
  const names = (kind) => [...new Set([...text.matchAll(new RegExp(`\\b${kind}\\.([A-Za-z_][A-Za-z0-9_]*)`, 'g'))].map((m) => m[1]))];
  return { secrets: names('secrets'), vars: names('vars') };
}

function gh(args, cwd, env) {
  try {
    const out = execFileSync('gh', args, { cwd, env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 20000 });
    return { ok: true, names: JSON.parse(out).map((x) => x.name) };
  } catch (e) {
    return { ok: false, why: e.code === 'ENOENT' ? 'gh is not installed' : String(e.stderr || e.message).trim().split('\n')[0] };
  }
}

function cronOf(doc) {
  const on = doc?.on ?? doc?.true;
  const s = on?.schedule;
  return Array.isArray(s) && s[0]?.cron ? String(s[0].cron) : '';
}

export async function doctor(argv, io) {
  let v;
  try {
    ({ values: v } = parseArgs({ args: argv, options: { dir: { type: 'string' }, 'no-gh': { type: 'boolean' }, help: { type: 'boolean', short: 'h' } }, strict: true }));
  } catch (e) {
    io.stderr(`dawnfix doctor: ${e.message}\n\n${DOCTOR_HELP}`);
    return 2;
  }
  if (v.help) {
    io.stdout(DOCTOR_HELP);
    return 0;
  }
  let failed = 0;
  const ok = (m) => io.stdout(`ok    ${m}\n`);
  const warn = (m) => io.stdout(`warn  ${m}\n`);
  const bad = (m) => {
    failed++;
    io.stdout(`FAIL  ${m}\n`);
  };
  const repo = detectRepo(v.dir || io.cwd);
  if (!repo) {
    io.stderr('dawnfix doctor: not inside a git repository\n');
    return 2;
  }
  const bbName = repo.bitbucket && `${repo.bitbucket.workspace}/${repo.bitbucket.slug}`;
  io.stdout(`Dawnfix doctor ${VERSION}: ${repo.slug || repo.gitlab?.path || bbName || repo.root}\n\n`);

  // 1. .dawnfix.yml
  const cfgPath = join(repo.root, '.dawnfix.yml');
  let config = null;
  if (!existsSync(cfgPath)) {
    bad('.dawnfix.yml is missing: run npx dawnfix init');
  } else {
    try {
      config = readYaml(cfgPath);
      const errors = validate(CONFIG_SCHEMA, config);
      if (errors.length) {
        bad(`.dawnfix.yml has ${errors.length} problem(s):`);
        for (const e of errors) io.stdout(`        ${e.path}: ${e.message}\n`);
        config = null;
      } else {
        const kinds = (config.sources || []).map((s) => Object.keys(s)[0]).join(', ');
        ok(`.dawnfix.yml is valid (${kinds}; autonomy ${config.autonomy || 'diagnose'})`);
      }
    } catch (e) {
      bad(`.dawnfix.yml is not valid YAML: ${e.message.split('\n')[0]}`);
    }
  }

  // 2. the workflow (GitHub), else a GitLab pipeline that includes the template
  const wf = findWorkflow(repo.root);
  const ciPath = join(repo.root, '.gitlab-ci.yml');
  const ci = !wf && existsSync(ciPath) ? readFileSync(ciPath, 'utf8') : '';
  if (ci && hasDawnfix(ci)) {
    const tag = /dawnfix\/dawnfix\/(v\d+\.\d+\.\d+)\/templates\/gitlab\//.exec(ci)?.[1];
    const integrity = /integrity:\s*["']?(sha256-[A-Za-z0-9+/=]+)/.exec(ci)?.[1];
    if (!/templates\/gitlab\/dawnfix\.gitlab-ci\.yml/.test(ci)) ok('.gitlab-ci.yml defines the Dawnfix jobs (a copy of the template)');
    else if (!tag) bad('.gitlab-ci.yml includes the Dawnfix template but not at a release tag: use the include lines of npx dawnfix init --host gitlab --dry-run');
    else if (!integrity) warn(`.gitlab-ci.yml includes the Dawnfix template of ${tag} without integrity: (GitLab then runs whatever that URL serves)`);
    else if (tag === `v${VERSION}` && integrity !== INTEGRITY) bad(`.gitlab-ci.yml: the integrity of the ${tag} template is ${INTEGRITY}, not ${integrity}`);
    else ok(`.gitlab-ci.yml includes the Dawnfix template of ${tag}, pinned with its integrity`);
    const sources = (config?.sources || []).map((s) => Object.keys(s)[0]);
    const vars = [...(sources.includes('aws') ? ['DAWNFIX_AWS_ROLE_ARN', 'DAWNFIX_AWS_REGION'] : []), ...(sources.includes('gcp') ? ['DAWNFIX_GCP_WIF_PROVIDER'] : [])];
    warn('GitLab: check by hand in Settings > CI/CD > Variables (and a pipeline schedule with DAWNFIX_RUN=true):');
    for (const [name, env, what] of GITLAB_SECRETS) io.stdout(`        secret ${name} (masked, protected, environment ${env}): ${what}\n`);
    for (const name of vars) io.stdout(`        variable ${name}\n`);
    ok('plan: Free & source available, unless DAWNFIX_ENTERPRISE_KEY is set (hosted reporting, Enterprise)');
    io.stdout(failed ? `\n${failed} check(s) failed.\n` : '\nAll checks passed.\n');
    return failed ? 1 : 0;
  }
  const bbPath = join(repo.root, 'bitbucket-pipelines.yml');
  const bb = !wf && !(ci && hasDawnfix(ci)) && existsSync(bbPath) ? readFileSync(bbPath, 'utf8') : '';
  if (bb && bbHasDawnfix(bb)) {
    const pinnedTo = bbVersionOf(bb);
    if (!pinnedTo) warn('bitbucket-pipelines.yml has the Dawnfix pipeline but no DAWNFIX_VERSION: take the steps of npx dawnfix init --host bitbucket --dry-run');
    else if (pinnedTo !== VERSION) warn(`bitbucket-pipelines.yml runs Dawnfix ${pinnedTo}; this is ${VERSION} (npx dawnfix init --host bitbucket --dry-run shows the new steps)`);
    else ok(`bitbucket-pipelines.yml has the Dawnfix custom pipeline of v${pinnedTo}`);
    if (/^\s*oidc:\s*true\s*$/m.test(bb) && (bb.match(/^\s*oidc:\s*true\s*$/gm) || []).length > 1) {
      bad('bitbucket-pipelines.yml: oidc: true on more than one step; only the read step may get the OIDC token');
    }
    const sources = (config?.sources || []).map((s) => Object.keys(s)[0]);
    const vars = [...(sources.includes('aws') ? ['DAWNFIX_AWS_ROLE_ARN', 'DAWNFIX_AWS_REGION'] : []), ...(sources.includes('gcp') ? ['DAWNFIX_GCP_WIF_PROVIDER'] : [])];
    warn('Bitbucket: check by hand in Repository settings > Deployments (and a schedule for custom: dawnfix):');
    for (const [name, env, type, what] of BITBUCKET_SECRETS) io.stdout(`        secret ${name} (secured, deployment environment ${env}, type ${type}): ${what}\n`);
    for (const name of vars) io.stdout(`        repository variable ${name}\n`);
    io.stdout('        no secret in repository or workspace variables (they reach every step)\n');
    // The push restriction on * (Bitbucket's git proxy reaches every step). Read with the user's own
    // token from BITBUCKET_TOKEN (BITBUCKET_EMAIL too for an Atlassian API token); only to api.bitbucket.org.
    if (bbName && process.env.BITBUCKET_TOKEN) {
      const tok = process.env.BITBUCKET_TOKEN;
      const auth = process.env.BITBUCKET_EMAIL
        ? `Basic ${Buffer.from(`${process.env.BITBUCKET_EMAIL}:${tok}`).toString('base64')}` : `Bearer ${tok}`;
      try {
        const res = await fetch(`https://api.bitbucket.org/2.0/repositories/${bbName}/branch-restrictions?pagelen=100`,
          { headers: { Authorization: auth, Accept: 'application/json' }, redirect: 'error' });
        if (!res.ok) bad(`Bitbucket branch restrictions: HTTP ${res.status} (the token needs repository admin)`);
        else {
          const v = pushRestrictionVerdict((await res.json()).values);
          (v.ok ? ok : bad)(`Bitbucket: ${v.why}`);
        }
      } catch (e) {
        bad(`Bitbucket branch restrictions: ${e.name}`);
      }
    } else {
      bad('Bitbucket: a push restriction on * letting only the publish account push is REQUIRED and was not checked:');
      io.stdout('        set BITBUCKET_TOKEN (and BITBUCKET_EMAIL for an Atlassian API token) and run doctor again;\n');
      io.stdout('        npx dawnfix init --host bitbucket --dry-run prints the command that sets it\n');
    }
    if (config && config.autonomy && config.autonomy !== 'diagnose') {
      warn(`Bitbucket: autonomy ${config.autonomy} changes code, which needs a self-hosted runner for the agent step `
        + '(Claude Code\'s sandbox cannot start on Bitbucket Cloud; the agent step refuses there). On Cloud use diagnose');
    }
    ok('plan: Free & source available, unless DAWNFIX_ENTERPRISE_KEY is set (hosted reporting, Enterprise)');
    io.stdout(failed ? `\n${failed} check(s) failed.\n` : '\nAll checks passed.\n');
    return failed ? 1 : 0;
  }
  let needs = { secrets: [AI_SECRET], vars: [] };
  let passesKey = false;
  if (!wf) {
    bad(`no Dawnfix workflow in .github/workflows/${ci ? ' and no Dawnfix include in .gitlab-ci.yml' : ''}${bb ? ' and no Dawnfix pipeline in bitbucket-pipelines.yml' : ''}: run npx dawnfix init`);
  } else {
    const text = readFileSync(join(repo.root, wf.file), 'utf8');
    if (wf.kind === 'caller') {
      const kind = pinned(wf.ref);
      if (!wf.ref) bad(`${wf.file} calls dawnfix.yml without a ref: add @v0 (or a release tag or commit SHA)`);
      else if (!kind) bad(`${wf.file} calls dawnfix.yml@${wf.ref}: not pinned to a release. Use @v0, @v${VERSION} or a commit SHA`);
      else ok(`${wf.file} calls dawnfix/dawnfix@${wf.ref} (${kind === 'sha' ? 'a commit SHA' : kind === 'release' ? 'an exact release' : 'the major release tag; pin v' + VERSION + ' or a SHA to freeze it'})`);
      const perms = wf.jobDoc.permissions ?? wf.doc.permissions ?? {};
      const missing = Object.entries(NEEDED_PERMISSIONS).filter(([k, val]) => perms[k] !== val).map(([k, val]) => `${k}: ${val}`);
      if (perms === 'write-all' || missing.length === 0) ok('permissions cover every job (each job narrows them)');
      else bad(`${wf.file} must grant ${missing.join(', ')} (GitHub refuses to start a run whose jobs ask for more than the caller grants)`);
      const wfNeeds = referenced(JSON.stringify(wf.jobDoc.with || {}) + JSON.stringify(wf.jobDoc.secrets || {}));
      if (wfNeeds.secrets.includes(FALLBACK_AI_SECRET) && !wfNeeds.secrets.includes(AI_SECRET)) {
        warn(`${wf.file} passes the deprecated ${FALLBACK_AI_SECRET} (fallback for this release only): pass ${AI_SECRET}: \${{ secrets.${AI_SECRET} }} instead`);
      }
      needs = { secrets: [...new Set([AI_SECRET, ...wfNeeds.secrets.filter((x) => x !== FALLBACK_AI_SECRET)])], vars: wfNeeds.vars.filter((x) => x !== 'DAWNFIX_AI_MODEL') };
      if (wf.jobDoc.secrets === 'inherit') {
        warn(`secrets: inherit passes every secret of the repo to the workflow; pass ${AI_SECRET} (and DAWNFIX_ENTERPRISE_KEY) by name`);
        needs.secrets = [AI_SECRET];
      }
      passesKey = wf.jobDoc.secrets === 'inherit' || ENTERPRISE.some((k) => wfNeeds.secrets.includes(k));
    } else {
      ok(`${wf.file} is the copy-it-yourself template of ${wf.ref}`);
      const r = referenced(text);
      needs = { secrets: [AI_SECRET], vars: r.vars.filter((x) => /ROLE_ARN|WIF_PROVIDER/.test(x)) };
      passesKey = true;
    }
    const cron = cronOf(wf.doc);
    if (config && cron) {
      const want = String(config.schedule || '17 * * * *').trim().split(/\s+/).join(' ');
      if (cron.trim().split(/\s+/).join(' ') === want) ok(`cron "${cron}" matches the schedule of .dawnfix.yml`);
      else warn(`cron "${cron}" differs from the schedule "${want}" of .dawnfix.yml`);
    } else if (!cron) {
      warn(`${wf.file} has no schedule: Dawnfix only runs when started by hand`);
    }
    const sources = (config?.sources || []).map((s) => Object.keys(s)[0]);
    if (sources.includes('aws') && !/aws-role-arn|DAWNFIX_AWS_ROLE_ARN/.test(text)) bad('an AWS source but no aws-role-arn in the workflow');
    if (sources.includes('gcp') && !/gcp-wif-provider|DAWNFIX_GCP_WIF_PROVIDER/.test(text)) bad('a GCP source but no gcp-wif-provider in the workflow');
  }

  // 3. names in the repo settings
  const required = needs.secrets.filter((s) => !ENTERPRISE.includes(s) && s !== 'DAWNFIX_PR_TOKEN' && s !== 'DAWNFIX_PR_APP_PRIVATE_KEY');
  let secretNames = null;
  if (!v['no-gh']) {
    const args = repo.slug ? ['-R', repo.slug] : [];
    const s = gh(['secret', 'list', ...args, '--json', 'name'], repo.root, io.env);
    const vars = gh(['variable', 'list', ...args, '--json', 'name'], repo.root, io.env);
    if (s.ok && vars.ok) {
      secretNames = s.names;
      for (const name of required) {
        if (s.names.includes(name)) ok(`secret ${name} is set`);
        else if (name === AI_SECRET && s.names.includes(FALLBACK_AI_SECRET)) warn(`secret ${FALLBACK_AI_SECRET} is set but deprecated (read as a fallback for this release only): gh secret set ${AI_SECRET}   (your AI API key, Claude today)`);
        else bad(`secret ${name} is not set: gh secret set ${name}${name === AI_SECRET ? '   (your AI API key, Claude today; an organization secret works too)' : ''}`);
      }
      for (const name of needs.vars) {
        if (vars.names.includes(name)) ok(`variable ${name} is set`);
        else bad(`variable ${name} is not set: gh variable set ${name} --body <value>`);
      }
    } else {
      warn(`could not list the repo's secrets with gh (${s.ok ? vars.why : s.why}). Check by hand in Settings > Secrets and variables > Actions:`);
      for (const name of required) io.stdout(`        secret ${name}\n`);
      for (const name of needs.vars) io.stdout(`        variable ${name}\n`);
    }
  } else {
    warn('--no-gh: check by hand in Settings > Secrets and variables > Actions:');
    for (const name of required) io.stdout(`        secret ${name}\n`);
    for (const name of needs.vars) io.stdout(`        variable ${name}\n`);
  }

  // 4. plan
  const keySet = secretNames && ENTERPRISE.some((k) => secretNames.includes(k));
  if (keySet && passesKey) ok('plan: Enterprise. The key is set; hosted reporting is on (the hosted service checks the key)');
  else if (keySet) warn('plan: an Enterprise key is set but the workflow does not pass DAWNFIX_ENTERPRISE_KEY to dawnfix.yml');
  else if (secretNames) ok('plan: Free & source available. Everything runs in your CI; nothing is sent to the hosted service');
  else ok('plan: Free & source available, unless DAWNFIX_ENTERPRISE_KEY is set (hosted reporting, Enterprise)');

  io.stdout(failed ? `\n${failed} check(s) failed.\n` : '\nAll checks passed.\n');
  return failed ? 1 : 0;
}
