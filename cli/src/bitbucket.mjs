// `npx dawnfix init --host bitbucket`: bitbucket-pipelines.yml (the release's template, bundled in
// at build time as its exact bytes; Bitbucket has no remote include), and the next steps (cloud
// trust, Pipelines, deployment environments, secured deployment variables, the schedule).
import TEMPLATE_BYTES from '../../templates/bitbucket/bitbucket-pipelines.yml';
import { RAW, REPO_URL, TAG } from './version.mjs';

export const TEMPLATE_PATH = 'templates/bitbucket/bitbucket-pipelines.yml';
export const TEMPLATE = new TextDecoder().decode(TEMPLATE_BYTES);
export const PIPELINE = 'dawnfix';
export const FILE = 'bitbucket-pipelines.yml';

/** Secured deployment variables: each in the one deployment environment whose step uses it. */
export const SECRETS = [
  ['DAWNFIX_AI_API_KEY', 'dawnfix-agent', 'Test', 'your AI API key (Claude today)'],
  ['DAWNFIX_HOST_TOKEN', 'dawnfix-publish', 'Staging',
    'a repository access token: scopes repository:write, pullrequest:write, pipeline:write'],
  ['DAWNFIX_ENTERPRISE_KEY', 'dawnfix-report', 'Production', 'optional, Enterprise only'],
];

/** The part of the template to merge into an existing bitbucket-pipelines.yml. */
export function snippet() {
  const i = TEMPLATE.search(/^definitions:/m);
  return i >= 0 ? TEMPLATE.slice(i) : TEMPLATE;
}

/** True when a bitbucket-pipelines.yml already defines the Dawnfix custom pipeline or steps. */
export function hasDawnfix(text) {
  return /^ {4}dawnfix:\s*$/m.test(text) && /dawnfix run (read|agent|publish)/.test(text)
    || /&dawnfix-(read|agent|publish)\b/.test(text);
}

/** The DAWNFIX_VERSION a pipelines file pins, or ''. */
export function versionOf(text) {
  return /export DAWNFIX_VERSION="([^"]+)"/.exec(text)?.[1] || '';
}

export function bitbucketNextSteps(a, repo, { wroteCi }) {
  const bb = repo.bitbucket || { workspace: 'WORKSPACE', slug: 'REPO' };
  const full = `${bb.workspace}/${bb.slug}`;
  const b = repo.branch;
  const out = ['Next steps. You run these; dawnfix never asks for or stores a secret.', ''];
  let n = 1;
  out.push(`${n++}. The UUIDs the cloud trust needs. Repository settings > Pipelines > OpenID Connect shows the`,
    '   identity provider URL and the audience (ari:cloud:bitbucket::workspace/<workspace UUID>). The repository',
    `   UUID (with its braces) is the "uuid" of GET https://api.bitbucket.org/2.0/repositories/${full}.`);
  if (a.cloud === 'aws') {
    out.push(`${n++}. The read-only AWS role (CloudFormation; logs and alarms read only, trusts only ${full}'s pipelines):`,
      `   ${REPO_URL}/blob/${TAG}/infra/aws/dawnfix-read-role-bitbucket.yaml`,
      `   curl -fsSLO ${RAW}/infra/aws/dawnfix-read-role-bitbucket.yaml`,
      '   aws cloudformation deploy --template-file dawnfix-read-role-bitbucket.yaml \\',
      `     --stack-name dawnfix-read-${bb.slug} --capabilities CAPABILITY_NAMED_IAM \\`,
      `     --parameter-overrides Workspace=${bb.workspace} WorkspaceUuid=<workspace UUID, no braces> \\`,
      `       RepositoryUuid='{<repository UUID>}' CreateOIDCProvider=true RoleName=dawnfix-read-${bb.slug} LogGroupPrefix='*'`,
      '   (The account has this workspace\'s OIDC provider already? CreateOIDCProvider=false and',
      `   ExistingOIDCProviderArn=<its ARN>: ${REPO_URL}/blob/${TAG}/infra/aws/README.md)`,
      `   Repository variables (Repository settings > Pipelines > Repository variables; not secured, not secrets):`,
      `   DAWNFIX_AWS_ROLE_ARN = ${a.awsRoleArn || `the RoleArn output of the stack dawnfix-read-${bb.slug}`}`,
      `   DAWNFIX_AWS_REGION = ${a.awsRegion}`);
  } else {
    out.push(`${n++}. Workload Identity Federation (roles/logging.viewer only, trusts only ${full}'s pipelines on ${b}):`,
      `   ${REPO_URL}/blob/${TAG}/infra/gcp/setup-wif-bitbucket.sh`,
      `   curl -fsSLO ${RAW}/infra/gcp/setup-wif-bitbucket.sh`,
      `   bash setup-wif-bitbucket.sh --branch ${b} ${bb.workspace} <workspace UUID> '{<repository UUID>}' ${a.gcpProject}`,
      '   Repository variable (not secured, not a secret):',
      `   DAWNFIX_GCP_WIF_PROVIDER = ${a.gcpWifProvider || 'the provider name setup-wif-bitbucket.sh prints'}`);
  }
  out.push(`${n++}. Turn Pipelines on: Repository settings > Pipelines > Settings > Enable Pipelines.`,
    `${n++}. Deployment environments (Repository settings > Deployments), one per secret, in Bitbucket's order:`,
    ...SECRETS.map(([, env, type]) => `   ${env.padEnd(16)} type ${type}`),
    `${n++}. Secrets: SECURED deployment variables, each in the one environment whose step uses it, so no other`,
    '   step ever holds it. Never put a secret in repository or workspace variables: those reach every step.',
    ...SECRETS.map(([name, env, , what]) => `   ${name.padEnd(23)} in ${env.padEnd(16)} ${what}`),
    '   The access token: Repository settings > Security > Access tokens. Or an Atlassian API token of a user,',
    '   with DAWNFIX_BITBUCKET_EMAIL (that account\'s email, not secured) in dawnfix-publish beside it.',
    `${n++}. ${wroteCi ? `Commit .dawnfix.yml and ${FILE}` : `Merge the Dawnfix part into ${FILE}, commit it with .dawnfix.yml`} on a branch, open a pull request and merge it.`,
    `${n++}. The schedule (keep it equal to the schedule of .dawnfix.yml): Repository settings > Pipelines > Schedules,`,
    `   branch ${b}, pipeline custom: ${PIPELINE}. The UI offers hourly, daily or weekly; the API takes a cron with`,
    '   seconds. With your own token in BITBUCKET_TOKEN (export it from a password manager; never printed):',
    `   curl -sS -X POST -H "Authorization: Bearer $BITBUCKET_TOKEN" -H 'Content-Type: application/json' \\`,
    `     https://api.bitbucket.org/2.0/repositories/${full}/pipelines_config/schedules/ \\`,
    `     -d '{"type":"pipeline_schedule","enabled":true,"cron_pattern":"${bitbucketCron(a.schedule)}",`
      + `"target":{"type":"pipeline_ref_target","ref_type":"branch","ref_name":"${b}","selector":{"type":"custom","pattern":"${PIPELINE}"}}}'`,
    `${n++}. REQUIRED: a push restriction on every branch, so only the account behind DAWNFIX_HOST_TOKEN can push.`,
    '   Every Bitbucket Pipelines step can push through Bitbucket\'s git proxy (localhost:29418) with the',
    '   pipeline\'s own credential, so this is what keeps the agent step from pushing. Free plan: yes.',
    ...pushRestrictionLines(full),
    `${n++}. A first run by hand: set the repository variable DAWNFIX_BASELINE=true (records what is already`,
    `   failing, opens nothing), then Pipelines > Run pipeline > branch ${b}, custom: ${PIPELINE}. Remove the`,
    '   variable afterwards. (DAWNFIX_DRY_RUN=true instead prints exactly what would leave your account.)',
    `${n++}. npx dawnfix doctor`);
  return out.join('\n') + '\n';
}

/** Why Bitbucket Cloud runs diagnose mode only (init says it; the agent step refuses fix mode there). */
export const BB_DIAGNOSE_ONLY = 'on Bitbucket Cloud Dawnfix runs in diagnose mode only (it files issues, it does not change '
  + 'code): every Pipelines step can push through Bitbucket\'s git proxy, and Claude Code\'s sandbox, which keeps the '
  + 'agent off it, cannot start in Bitbucket Cloud\'s step containers. .dawnfix.yml gets autonomy: diagnose.';
export const BB_FIX_REFUSED = 'plan and draft-pr change code, which on Bitbucket needs a self-hosted runner for the '
  + 'agent step: a Linux runner where bwrap can create user and network namespaces (unprivileged user namespaces on; '
  + 'with the Docker runner, a seccomp/AppArmor profile that allows them), with bubblewrap, socat, Node 20+ and '
  + 'Python 3.11+. On such a runner, run init again with --self-hosted-runner. On Bitbucket Cloud use --autonomy diagnose.';

/** The lines that set the push restriction on `*` (Bitbucket's branch restrictions API). */
export function pushRestrictionLines(full) {
  return [
    '   The UUID of that account: for an Atlassian API token, GET /2.0/user with it (`uuid`); for a',
    '   repository access token, its bot user (Repository settings > Branch restrictions lists it by name).',
    '   With an admin\'s token in BITBUCKET_TOKEN (export it from a password manager; never printed):',
    `   curl -sS -X POST -H "Authorization: Bearer $BITBUCKET_TOKEN" -H 'Content-Type: application/json' \\`,
    `     https://api.bitbucket.org/2.0/repositories/${full}/branch-restrictions \\`,
    `     -d '{"kind":"push","branch_match_kind":"glob","pattern":"*","users":[{"uuid":"{<account UUID>}"}],"groups":[]}'`,
    '   (Or Repository settings > Branch restrictions > Add: pattern *, Write access: only that account.)',
  ];
}

/** A five-field cron as Bitbucket's seven-field one (seconds first, year last, ? for day-of-week). */
export function bitbucketCron(cron) {
  const f = String(cron || '17 * * * *').trim().split(/\s+/);
  if (f.length !== 5) return '0 17 * * * ? *';
  const [min, hour, dom, mon, dow] = f;
  return dow === '*' ? `0 ${min} ${hour} ${dom} ${mon} ? *` : `0 ${min} ${hour} ? ${mon} ${dow} *`;
}
