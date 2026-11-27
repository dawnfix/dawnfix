// The token permissions the audit reads with, in one place: the README table, the CI setup
// prompt (prompts/flare-ci.md) and the /flare page all show this list (tests compare them).

export interface TokenPermission {
  /** Where it sits in the dashboard's "Create Custom Token" form. */
  readonly scope: 'Account' | 'User' | 'Zone';
  /** The permission group's dashboard name. */
  readonly group: string;
  readonly level: 'Read';
  readonly usedFor: string;
  /** The audit runs without it; the checks it feeds say "not checked". */
  readonly optional: boolean;
}

export const TOKEN_PERMISSIONS: readonly TokenPermission[] = [
  {
    scope: 'Account',
    group: 'Workers Scripts',
    level: 'Read',
    usedFor: 'scripts, workers.dev / preview flags, bindings, secret **names**, deployments, cron schedules, custom domains, account workers.dev subdomain',
    optional: false,
  },
  { scope: 'Account', group: 'Access: Apps and Policies', level: 'Read', usedFor: 'which hostnames and workers.dev URLs Access protects', optional: false },
  { scope: 'Account', group: 'Account Settings', level: 'Read', usedFor: 'account list and names', optional: false },
  { scope: 'Account', group: 'Account API Tokens', level: 'Read', usedFor: 'account-owned tokens and their permission group names (optional)', optional: true },
  { scope: 'User', group: 'API Tokens', level: 'Read', usedFor: 'user-owned tokens (optional; only on a user-owned token)', optional: true },
  { scope: 'Zone', group: 'Zone', level: 'Read', usedFor: 'zone list', optional: false },
  { scope: 'Zone', group: 'Workers Routes', level: 'Read', usedFor: 'zone Workers routes', optional: false },
  { scope: 'Zone', group: 'DNS', level: 'Read', usedFor: 'DNS records', optional: false },
  { scope: 'Zone', group: 'Zone Settings', level: 'Read', usedFor: 'min TLS, Always Use HTTPS, HSTS', optional: false },
];

/** "Account > Workers Scripts > Read", the way the dashboard form reads. */
export const permissionLine = (p: TokenPermission): string => `${p.scope} > ${p.group} > ${p.level}`;
