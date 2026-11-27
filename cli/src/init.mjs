// npx dawnfix init: writes .dawnfix.yml and a short caller of the reusable workflow, after
// showing both in full. Never asks for, reads or writes a secret: it prints the `gh secret set`
// lines for the user to run.
import { createInterface } from 'node:readline/promises';
import { parseArgs } from 'node:util';
import { parse as parseYaml } from 'yaml';
import CONFIG_SCHEMA from '../../core/schema/config.schema.json';
import { detectCommands, detectRepo } from './repo.mjs';
import { checkTarget, safeWrite, UnsafePath } from './safe-write.mjs';
import { validate } from './schema.mjs';
import { MAJOR_REF, RAW, REPO_URL, TAG, VERSION } from './version.mjs';

export const INIT_HELP = `Usage: dawnfix init [options]

Sets Dawnfix up in the git repo you are in: shows .dawnfix.yml and
.github/workflows/dawnfix.yml in full, writes them when you confirm (or with --yes),
and prints the commands you run next (the read-only cloud role, gh secret set).
It never asks for a secret and never writes one.

Options:
  --cloud aws|gcp            Where the logs are (asked if missing; default aws)
  --aws-region REGION        Region of the log groups (default us-east-1)
  --log-group NAME           CloudWatch log group to watch (repeatable)
  --alarms / --no-alarms     Also report CloudWatch alarms in ALARM (default: on when no log group)
  --aws-role-arn ARN         The read-only role, if it exists already (else a repo variable)
  --gcp-project ID           GCP project whose Cloud Logging is read
  --gcp-wif-provider NAME    Workload identity provider, if it exists already (else a repo variable)
  --autonomy LEVEL           diagnose | plan | draft-pr (default diagnose: issues only)
  --test-command CMD         The one command the fix agent may run (plan, draft-pr)
  --install-command CMD      Installs dependencies before the fix agent runs (plan, draft-pr)
  --schedule CRON            When the read job runs (default "17 * * * *", hourly)
  --ref REF                  Ref of dawnfix/dawnfix to call (default ${MAJOR_REF}; a tag or commit SHA)
  --enterprise               Also send closed-PR events (hosted PR tracking, Enterprise key)
  --dir DIR                  The repo (default: the current directory)
  --yes, -y                  Write without asking
  --dry-run                  Show the files and the next steps; write nothing
  --force                    Replace files that exist
  -h, --help                 This help
`;

const OPTIONS = {
  cloud: { type: 'string' },
  'aws-region': { type: 'string' },
  'log-group': { type: 'string', multiple: true },
  alarms: { type: 'boolean' },
  'no-alarms': { type: 'boolean' },
  'aws-role-arn': { type: 'string' },
  'gcp-project': { type: 'string' },
  'gcp-wif-provider': { type: 'string' },
  autonomy: { type: 'string' },
  'test-command': { type: 'string' },
  'install-command': { type: 'string' },
  schedule: { type: 'string' },
  ref: { type: 'string' },
  enterprise: { type: 'boolean' },
  dir: { type: 'string' },
  yes: { type: 'boolean', short: 'y' },
  'dry-run': { type: 'boolean' },
  force: { type: 'boolean' },
  help: { type: 'boolean', short: 'h' },
};

const q = (s) => JSON.stringify(String(s));

export function renderConfig(a) {
  const lines = [
    '# .dawnfix.yml: what Dawnfix watches and what it may do. Written by `npx dawnfix init`.',
    `# Every key: ${REPO_URL}/blob/${TAG}/templates/dawnfix.yml`,
    '# Check it with: npx dawnfix doctor',
    'version: 1',
    '',
    '# diagnose: an issue per new error | plan: an issue with the planned fix | draft-pr: draft PRs.',
    `autonomy: ${a.autonomy}`,
    '',
    '# Keep it equal to the cron in .github/workflows/dawnfix.yml. Off the hour.',
    `schedule: ${q(a.schedule)}`,
    '',
    'sources:',
  ];
  if (a.cloud === 'aws') {
    lines.push('  - aws:', `      region: ${a.awsRegion}`);
    if (a.logGroups.length) lines.push('      log_groups:', ...a.logGroups.map((g) => `        - ${q(g)}`));
    if (a.alarms) lines.push('      alarms: true                 # alarms currently in ALARM');
  } else {
    lines.push('  - gcp:', `      project: ${a.gcpProject}`, "      filter: 'severity>=ERROR'");
  }
  if (a.testCommand) {
    lines.push('', '# The one command the fix agent may run (its only shell permission). Plain words only.',
      'test:', `  command: ${q(a.testCommand)}`);
  }
  lines.push('', 'report:', '  issues: github', '');
  return lines.join('\n');
}

export function renderCaller(a) {
  const withLines = [];
  if (a.cloud === 'aws') withLines.push(`aws-role-arn: ${a.awsRoleArn || '${{ vars.DAWNFIX_AWS_ROLE_ARN }}'}`);
  else withLines.push(`gcp-wif-provider: ${a.gcpWifProvider || '${{ vars.DAWNFIX_GCP_WIF_PROVIDER }}'}`);
  if (a.installCommand) withLines.push(`install-command: ${q(a.installCommand)}`);
  return [
    `# Dawnfix (${REPO_URL}), written by \`npx dawnfix init\`. The jobs are in the`,
    '# reusable workflow below; each asks for less than the permissions granted here.',
    'name: dawnfix',
    'on:',
    `  schedule: [{ cron: ${q(a.schedule)} }] # the \`schedule\` of .dawnfix.yml`,
    '  workflow_dispatch: { inputs: { baseline: { type: boolean }, dry_run: { type: boolean } } }',
    ...(a.enterprise ? ['  pull_request: { types: [closed] } # hosted PR tracking (Enterprise)'] : []),
    'permissions: { contents: write, pull-requests: write, issues: write, id-token: write }',
    'jobs:',
    '  dawnfix:',
    `    uses: dawnfix/dawnfix/.github/workflows/dawnfix.yml@${a.ref}`,
    '    with:',
    ...withLines.map((l) => `      ${l}`),
    '    secrets:',
    '      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}',
    '      DAWNFIX_ENTERPRISE_KEY: ${{ secrets.DAWNFIX_ENTERPRISE_KEY }} # optional',
    '',
  ].join('\n');
}

export function nextSteps(a, repo) {
  const [org, name] = (repo.slug || 'OWNER/REPO').split('/');
  const out = ['Next steps. You run these; dawnfix never asks for or stores a secret.', ''];
  let n = 1;
  if (a.cloud === 'aws') {
    out.push(`${n++}. The read-only AWS role (CloudFormation; logs and alarms read only, trusts only ${org}/${name} on ${repo.branch}):`,
      `   ${REPO_URL}/blob/${TAG}/infra/aws/dawnfix-read-role.yaml`,
      `   curl -fsSLO ${RAW}/infra/aws/dawnfix-read-role.yaml`,
      '   aws cloudformation deploy --template-file dawnfix-read-role.yaml \\',
      `     --stack-name dawnfix-read-${name} --capabilities CAPABILITY_NAMED_IAM \\`,
      `     --parameter-overrides GitHubOrg=${org} GitHubRepo=${name} Branch=${repo.branch} \\`,
      `       CreateOIDCProvider=true RoleName=dawnfix-read-${name} LogGroupPrefix='*'`,
      `   (The account has GitHub's OIDC provider already? CreateOIDCProvider=false and`,
      `   ExistingOIDCProviderArn=<its ARN>: ${REPO_URL}/blob/${TAG}/infra/aws/README.md)`);
    if (!a.awsRoleArn) {
      out.push(`   gh variable set DAWNFIX_AWS_ROLE_ARN --body "$(aws cloudformation describe-stacks --stack-name dawnfix-read-${name} \\`,
        `     --query \"Stacks[0].Outputs[?OutputKey=='RoleArn'].OutputValue\" --output text)"`);
    }
  } else {
    out.push(`${n++}. Workload Identity Federation (roles/logging.viewer only, trusts only ${org}/${name} on ${repo.branch}):`,
      `   ${REPO_URL}/blob/${TAG}/infra/gcp/setup-wif.sh`,
      `   curl -fsSLO ${RAW}/infra/gcp/setup-wif.sh`,
      `   bash setup-wif.sh --branch ${repo.branch} ${a.gcpProject} ${org}/${name}`);
    if (!a.gcpWifProvider) out.push('   gh variable set DAWNFIX_GCP_WIF_PROVIDER --body "<the provider name setup-wif.sh prints>"');
  }
  out.push(`${n++}. Secrets (gh asks for the value and does not echo it):`,
    '   gh secret set ANTHROPIC_API_KEY',
    '   gh secret set DAWNFIX_ENTERPRISE_KEY   # optional, Enterprise only: turns on hosted reporting',
    `${n++}. Commit both files on a branch, open a pull request and merge it.`,
    `${n++}. gh workflow run dawnfix.yml -f dry_run=true   # prints exactly what would leave your account`,
    '   gh workflow run dawnfix.yml -f baseline=true  # records what is already failing, opens nothing',
    `${n++}. npx dawnfix doctor`);
  return out.join('\n') + '\n';
}

function fail(io, msg) {
  io.stderr(`dawnfix init: ${msg}\n`);
  return 2;
}

export async function init(argv, io) {
  let v;
  try {
    ({ values: v } = parseArgs({ args: argv, options: OPTIONS, allowPositionals: false, strict: true }));
  } catch (e) {
    return fail(io, `${e.message}\n\n${INIT_HELP}`);
  }
  if (v.help) {
    io.stdout(INIT_HELP);
    return 0;
  }
  const repo = detectRepo(v.dir || io.cwd);
  if (!repo) return fail(io, 'not inside a git repository: run it at the root of the repo Dawnfix should watch');
  if (!repo.slug) io.stderr('dawnfix init: no GitHub remote named origin; the next steps say OWNER/REPO\n');

  const ask = io.isTTY && !v.yes ? createInterface({ input: io.stdin, output: io.stdoutStream }) : null;
  const prompt = async (text, dflt) => {
    if (!ask) return dflt;
    const answer = (await ask.question(`${text}${dflt ? ` [${dflt}]` : ''}: `)).trim();
    return answer || dflt;
  };
  try {
    const guess = detectCommands(repo.root);
    const a = { ref: v.ref || MAJOR_REF, enterprise: Boolean(v.enterprise), schedule: v.schedule || '17 * * * *' };
    a.cloud = v.cloud || (v['gcp-project'] ? 'gcp' : await prompt('Where are the logs: aws or gcp', 'aws'));
    if (!['aws', 'gcp'].includes(a.cloud)) return fail(io, `--cloud must be aws or gcp, not ${q(a.cloud)}`);
    a.logGroups = [];
    if (a.cloud === 'aws') {
      a.awsRegion = v['aws-region'] || (await prompt('AWS region of the log groups', 'us-east-1'));
      a.logGroups = v['log-group'] || (await prompt('CloudWatch log groups to watch, comma separated (blank: alarms only)', ''))
        .split(',').map((s) => s.trim()).filter(Boolean);
      a.alarms = v['no-alarms'] ? false : v.alarms ?? (a.logGroups.length === 0 ? true : (await prompt('Also report alarms in ALARM (y/n)', 'y')).startsWith('y'));
      a.awsRoleArn = v['aws-role-arn'] || (await prompt('Read-only role ARN, if it exists (blank: set it up next)', ''));
    } else {
      a.gcpProject = v['gcp-project'] || (await prompt('GCP project id', ''));
      if (!a.gcpProject) return fail(io, '--gcp-project is required with --cloud gcp');
      a.gcpWifProvider = v['gcp-wif-provider'] || (await prompt('Workload identity provider, if it exists (blank: set it up next)', ''));
    }
    a.autonomy = v.autonomy || (await prompt('Autonomy: diagnose (issues only), plan or draft-pr', 'diagnose'));
    if (!['diagnose', 'plan', 'draft-pr'].includes(a.autonomy)) return fail(io, `--autonomy must be diagnose, plan or draft-pr, not ${q(a.autonomy)}`);
    const fixes = a.autonomy !== 'diagnose';
    a.testCommand = v['test-command'] ?? (fixes ? await prompt('Test command the fix agent may run', guess.test) : guess.test);
    a.installCommand = v['install-command'] ?? (fixes ? await prompt('Install command before the fix agent runs', guess.install) : '');
    if (a.autonomy === 'draft-pr' && !a.testCommand) {
      io.stderr('dawnfix init: draft-pr without a test command can only open issues (no failing test, no PR)\n');
    }
    if (a.awsRoleArn && !/^arn:aws[a-z-]*:iam::\d{1,12}:role\/[\w+=,.@/-]+$/.test(a.awsRoleArn)) {
      return fail(io, `--aws-role-arn ${q(a.awsRoleArn)} is not an IAM role ARN`);
    }
    if (!/^(v\d+(\.\d+){0,2}|[0-9a-f]{40})$/.test(a.ref)) return fail(io, `--ref must be a release tag (v0, v0.3.0) or a commit SHA, not ${q(a.ref)}`);

    const config = renderConfig(a);
    const errors = validate(CONFIG_SCHEMA, parseYaml(config));
    if (errors.length) return fail(io, `these settings make an invalid .dawnfix.yml:\n${errors.map((e) => `  ${e.path}: ${e.message}`).join('\n')}`);
    const files = [
      ['.dawnfix.yml', config],
      ['.github/workflows/dawnfix.yml', renderCaller(a)],
    ];
    let exists;
    try {
      exists = files.filter(([p]) => checkTarget(repo.root, p).exists).map(([p]) => p);
    } catch (e) {
      if (e instanceof UnsafePath) return fail(io, e.message);
      throw e;
    }

    io.stdout(`Dawnfix ${VERSION} in ${repo.slug || repo.root}. ${v['dry-run'] ? 'Dry run: nothing is written.' : 'These files will be written:'}\n`);
    for (const [p, text] of files) {
      io.stdout(`\n--- ${p}${exists.includes(p) ? ' (exists; replaced only with --force)' : ''}\n${text}`);
    }
    io.stdout('---\n\n');
    if (v['dry-run']) {
      io.stdout(nextSteps(a, repo));
      return 0;
    }
    if (exists.length && !v.force) return fail(io, `${exists.join(' and ')} exist already; re-run with --force to replace, or run npx dawnfix doctor`);
    if (!v.yes) {
      if (!ask) return fail(io, 'not a terminal: re-run with --yes to write these files (or --dry-run to only show them)');
      const ok = (await ask.question('Write these files? [y/N]: ')).trim().toLowerCase();
      if (!ok.startsWith('y')) {
        io.stdout('Nothing written.\n');
        return 1;
      }
    }
    for (const [p, text] of files) {
      try {
        safeWrite(repo.root, p, text, { overwrite: Boolean(v.force) });
      } catch (e) {
        if (e instanceof UnsafePath) return fail(io, e.message);
        throw e;
      }
      io.stdout(`wrote ${p}\n`);
    }
    io.stdout(`\n${nextSteps(a, repo)}`);
    return 0;
  } finally {
    ask?.close();
  }
}
