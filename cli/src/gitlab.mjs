// `npx dawnfix init --host gitlab`: the .gitlab-ci.yml that includes the release's template with
// GitLab's `integrity:` check, and the next steps (cloud trust, glab variable set, the schedule).
// The template is bundled in at build time (esbuild binary loader: the file's exact bytes), so
// the hash always matches the template published at this CLI's tag.
import { createHash } from 'node:crypto';
import TEMPLATE_BYTES from '../../templates/gitlab/dawnfix.gitlab-ci.yml';
import { RAW, REPO_URL, TAG } from './version.mjs';

export const TEMPLATE_PATH = 'templates/gitlab/dawnfix.gitlab-ci.yml';
export const TEMPLATE_URL = `${RAW}/${TEMPLATE_PATH}`;
/** GitLab's include integrity: sha256-<base64 of the sha256 of the template's bytes>. */
export const INTEGRITY = `sha256-${createHash('sha256').update(TEMPLATE_BYTES).digest('base64')}`;
export const JOBS = ['dawnfix-read', 'dawnfix-agent', 'dawnfix-publish', 'dawnfix-report'];

/** Secret CI/CD variables: each masked, protected and scoped to the one environment that uses it. */
export const SECRETS = [
  ['DAWNFIX_AI_API_KEY', 'dawnfix-agent', 'your AI API key (Claude today)'],
  ['DAWNFIX_HOST_TOKEN', 'dawnfix-publish', 'a project access token: role Developer, scopes api and write_repository'],
  ['DAWNFIX_ENTERPRISE_KEY', 'dawnfix-report', 'optional, Enterprise only'],
];

export function includeSnippet() {
  return ['include:', `  - remote: ${TEMPLATE_URL}`, `    integrity: ${INTEGRITY}`, ''].join('\n');
}

/** True when a .gitlab-ci.yml already includes the Dawnfix template or defines its jobs. */
export function hasDawnfix(text) {
  return /templates\/gitlab\/dawnfix\.gitlab-ci\.yml/.test(text) || new RegExp(`^(${JOBS.join('|')}):`, 'm').test(text);
}

export function renderGitlabCi(a) {
  const cloudVars = a.cloud === 'aws' ? '  DAWNFIX_AWS_ROLE_ARN, DAWNFIX_AWS_REGION' : '  DAWNFIX_GCP_WIF_PROVIDER';
  return [
    `# Dawnfix (${REPO_URL}), written by \`npx dawnfix init --host gitlab\`.`,
    `# The jobs (${JOBS.join(', ')}) are in the template`,
    `# below, at release ${TAG}.`,
    '# integrity: GitLab fetches the template and refuses to run the pipeline unless the',
    '# sha256 of its bytes equals this hash, so you run exactly what was published at that tag.',
    '# To upgrade, take the new include lines from `npx dawnfix@latest init --host gitlab --dry-run`.',
    '# The jobs run only in pipelines with DAWNFIX_RUN=true (the schedule); other pipelines are untouched.',
    '#',
    '# CI/CD variables (Settings > CI/CD > Variables; `npx dawnfix init` prints the glab lines):',
    ...SECRETS.map(([name, env, what]) => `#   ${name.padEnd(23)} masked, protected, environment ${env}:\n#   ${''.padEnd(23)} ${what}`),
    `# Not secret:${cloudVars.slice(1)}`,
    '# Optional: DAWNFIX_AUTONOMY, DAWNFIX_AI_MODEL, DAWNFIX_INSTALL_COMMAND',
    includeSnippet(),
  ].join('\n');
}

export function gitlabNextSteps(a, repo, { wroteCi }) {
  const gl = repo.gitlab || { host: 'gitlab.com', path: 'GROUP/PROJECT' };
  const name = gl.path.split('/').pop();
  const selfManaged = gl.host !== 'gitlab.com';
  const b = repo.branch;
  const out = ['Next steps. You run these; dawnfix never asks for or stores a secret.', ''];
  let n = 1;
  if (a.cloud === 'aws') {
    out.push(`${n++}. The read-only AWS role (CloudFormation; logs and alarms read only, trusts only ${gl.path} on ${b}):`,
      `   ${REPO_URL}/blob/${TAG}/infra/aws/dawnfix-read-role-gitlab.yaml`,
      `   curl -fsSLO ${RAW}/infra/aws/dawnfix-read-role-gitlab.yaml`,
      '   aws cloudformation deploy --template-file dawnfix-read-role-gitlab.yaml \\',
      `     --stack-name dawnfix-read-${name} --capabilities CAPABILITY_NAMED_IAM \\`,
      `     --parameter-overrides ProjectPath=${gl.path} Branch=${b} \\`,
      `       CreateOIDCProvider=true RoleName=dawnfix-read-${name} LogGroupPrefix='*'${selfManaged ? ` GitLabUrl=https://${gl.host}` : ''}`,
      '   (The account has the GitLab OIDC provider already? CreateOIDCProvider=false and',
      `   ExistingOIDCProviderArn=<its ARN>: ${REPO_URL}/blob/${TAG}/infra/aws/README.md)`);
    if (a.awsRoleArn) out.push(`   glab variable set DAWNFIX_AWS_ROLE_ARN --value "${a.awsRoleArn}"`);
    else {
      out.push(`   glab variable set DAWNFIX_AWS_ROLE_ARN --value "$(aws cloudformation describe-stacks --stack-name dawnfix-read-${name} \\`,
        `     --query "Stacks[0].Outputs[?OutputKey=='RoleArn'].OutputValue" --output text)"`);
    }
    out.push(`   glab variable set DAWNFIX_AWS_REGION --value ${a.awsRegion}`);
  } else {
    out.push(`${n++}. Workload Identity Federation (roles/logging.viewer only, trusts only ${gl.path} on ${b}):`,
      `   ${REPO_URL}/blob/${TAG}/infra/gcp/setup-wif-gitlab.sh`,
      `   curl -fsSLO ${RAW}/infra/gcp/setup-wif-gitlab.sh`,
      `   bash setup-wif-gitlab.sh --branch ${b}${selfManaged ? ` --gitlab-url https://${gl.host}` : ''} ${a.gcpProject} ${gl.path}`,
      `   glab variable set DAWNFIX_GCP_WIF_PROVIDER --value "${a.gcpWifProvider || '<the provider name setup-wif-gitlab.sh prints>'}"`);
  }
  const [ai, host, ent] = SECRETS;
  const set = ([v, env]) => `glab variable set ${v} --masked --protected --scope ${env}`;
  out.push(`${n++}. Secrets: masked, protected, each scoped to the one environment (job) that uses it, so no`,
    '   other job ever holds it. glab reads each value from stdin: `read -rs` keeps it off the screen and',
    '   out of your shell history, and the access token goes from glab to glab without being shown.',
    `   read -rs V && printf %s "$V" | ${set(ai)}; unset V   # ${ai[2]}`,
    `   glab token create dawnfix --access-level developer --scope api --scope write_repository --duration 365d \\`,
    `     | tr -d '\\n' | ${set(host)}`,
    '     # the project access token (role Developer, scopes api and write_repository). Or create it in',
    '     # Settings > Access tokens and set it with a read -rs line like the first.',
    `   read -rs V && printf %s "$V" | ${set(ent)}; unset V   # ${ent[2]}`,
    `   Protected variables reach protected branches only: keep ${b} protected (the default).`,
    '   Recommended: the runner feature flag FF_GIT_URLS_WITHOUT_TOKENS, and the job token limited',
    '   (Settings > CI/CD > Job token permissions). The agent job never clones and unsets every CI token.',
    `${n++}. ${wroteCi ? 'Commit .dawnfix.yml and .gitlab-ci.yml' : 'Add the include to .gitlab-ci.yml, commit it with .dawnfix.yml'} on a branch, open a merge request and merge it.`,
    `${n++}. The schedule (the jobs run only when DAWNFIX_RUN is true; keep the cron equal to .dawnfix.yml):`,
    '   New projects block pipeline variables, which the schedule needs for DAWNFIX_RUN. Allow them for maintainers',
    '   (Settings > CI/CD > Variables > Minimum role to use pipeline variables), or:',
    `   glab api --method PUT "projects/:fullpath" --field ci_pipeline_variables_minimum_override_role=maintainer`,
    `   glab schedule create --cron "${a.schedule}" --ref ${b} --description dawnfix --variable "DAWNFIX_RUN:true"`,
    `${n++}. A first run by hand (or Build > Pipelines > Run pipeline with these variables):`,
    `   glab ci run --branch ${b} --variables DAWNFIX_RUN:true --variables DAWNFIX_DRY_RUN:true   # prints exactly what would leave your account`,
    `   glab ci run --branch ${b} --variables DAWNFIX_RUN:true --variables DAWNFIX_BASELINE:true  # records what is already failing, opens nothing`,
    `${n++}. npx dawnfix doctor`);
  return out.join('\n') + '\n';
}
