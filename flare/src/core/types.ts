// The shapes every part shares. Collected data (Snapshot) is plain JSON so it can be
// recorded, replayed in tests, or kept by a Worker between cron runs.

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export const SEVERITIES: readonly Severity[] = ['critical', 'high', 'medium', 'low', 'info'];
export const severityRank = (s: Severity): number => SEVERITIES.length - SEVERITIES.indexOf(s);

/** Every check, in report order. The ingest schema (schema/flare-ingest.schema.json) lists the same ids. */
export const CHECK_IDS = [
  'workers-dev-enabled',
  'preview-urls-enabled',
  'hostname-without-auth',
  'ratelimit-namespace-shared',
  'route-to-missing-script',
  'dangling-dns',
  'dead-script',
  'compat-date-old',
  'secrets-changed',
  'token-over-scoped',
  'token-no-expiry',
  'token-unused',
  'zone-tls',
] as const;
export type CheckId = (typeof CHECK_IDS)[number];

export interface Finding {
  check: CheckId;
  severity: Severity;
  /** Account name or id, or "local" for a finding from wrangler files alone. */
  account: string;
  /** The thing the finding is about: a script, hostname, zone, token name, file. */
  resource: string;
  title: string;
  detail: string;
  fix: string;
  source: 'api' | 'local' | 'api+local';
}

/** A part of the account that could not be read, so its checks did not run. */
export interface CoverageGap {
  account: string;
  what: string;
  reason: string;
}

// ---- Cloudflare data, trimmed to what the checks read -----------------------------------

export interface CfScript {
  name: string;
  createdOn?: string;
  modifiedOn?: string;
  compatibilityDate?: string;
  handlers: string[];
  /** Route patterns the scripts list reports for this script (zone routes). */
  routes: string[];
  /** Latest deployment time, when the deployments endpoint answered. */
  lastDeployedOn?: string;
  subdomain?: { enabled: boolean; previewsEnabled: boolean };
  bindings?: CfBinding[];
  /** Cron expressions from the schedules endpoint. */
  crons?: string[];
  /** Secret NAMES only. Values are dropped in the client before they reach this shape. */
  secretNames?: string[];
}

export interface CfBinding {
  type: string;
  name: string;
  namespaceId?: string;
  /** Target script of a service binding. */
  service?: string;
}

export interface CfCustomDomain {
  hostname: string;
  service: string;
  zoneId?: string;
  zoneName?: string;
}

export interface CfZoneSettings {
  minTlsVersion?: string;
  alwaysUseHttps?: string;
  hsts?: { enabled: boolean; maxAge: number; includeSubdomains: boolean };
}

export interface CfRoute {
  id: string;
  pattern: string;
  script?: string;
}

export interface CfDnsRecord {
  id: string;
  type: string;
  name: string;
  content: string;
  proxied?: boolean;
}

export interface CfZone {
  id: string;
  name: string;
  status?: string;
  routes?: CfRoute[];
  dns?: CfDnsRecord[];
  settings?: CfZoneSettings;
}

export interface CfAccessApp {
  id?: string;
  name?: string;
  type?: string;
  /** Every hostname[/path] the app protects: domain, self_hosted_domains, public destinations. */
  domains: string[];
  /** Scripts named by `worker` destinations (their workers.dev and preview URLs). Unverified field shape. */
  workers?: string[];
  /** An `all_workers` destination: every workers.dev and preview URL in the account. Unverified field shape. */
  allWorkers?: boolean;
}

export interface CfTokenPolicy {
  effect: 'allow' | 'deny';
  /** Group names; a group listed by id only is resolved through the permission-groups list. */
  permissionGroups: string[];
  /** Group ids as the API returned them, when it did. */
  permissionGroupIds?: string[];
  resources: string[];
}

export interface CfToken {
  id: string;
  name: string;
  status?: string;
  expiresOn?: string;
  lastUsedOn?: string;
  issuedOn?: string;
  ipRestricted: boolean;
  policies: CfTokenPolicy[];
  scope: 'user' | 'account';
}

export interface AccountSnapshot {
  id: string;
  name: string;
  workersSubdomain?: string;
  scripts?: CfScript[];
  customDomains?: CfCustomDomain[];
  zones?: CfZone[];
  accessApps?: CfAccessApp[];
  tokens?: CfToken[];
  gaps: CoverageGap[];
}

// ---- Local wrangler files ---------------------------------------------------------------

export interface LocalWorker {
  /** The deployed Worker name: top-level name, or name-<env> for a [env.x] section. */
  name: string;
  file: string;
  env?: string;
  compatibilityDate?: string;
  /** undefined means the key is absent from the file, which is not the same as false. */
  workersDev?: boolean;
  previewUrls?: boolean;
  routes: { pattern: string; customDomain: boolean }[];
  ratelimitNamespaces: { binding: string; namespaceId: string }[];
  /** Auth markers found in the repo's source, e.g. a login route or an Access JWT check. */
  authMarkers: string[];
  /** `triggers.crons` from the config (inherited by environments, as in wrangler). */
  crons?: string[];
  /**
   * What the Worker's source looks like it exports, from a text search (src/node/scan.ts):
   * a fetch handler, a scheduled handler, or a default export that is not an object literal
   * (a framework app such as Hono, whose fetch the search cannot see). Absent when no
   * source was read.
   */
  entry?: { fetch: boolean; scheduled: boolean; opaqueDefault: boolean };
}

export interface Snapshot {
  takenAt: string;
  accounts: AccountSnapshot[];
  local: LocalWorker[];
  localGaps: CoverageGap[];
}

// ---- Options ----------------------------------------------------------------------------

export interface AuditOptions {
  /** Hostnames meant to be public. Exact names or "*.example.com" wildcards. */
  publicHostnames: string[];
  /** Scripts that do their own sign-in, declared by hand when no repo is scanned. */
  appAuthScripts: string[];
  staleDays: number;
  compatMonths: number;
  /** Per-account secret names from the previous run, keyed "<accountId>/<script>". */
  secretsBaseline?: Record<string, string[]>;
  now: Date;
}

export const DEFAULT_OPTIONS: Omit<AuditOptions, 'now'> = {
  publicHostnames: [],
  appAuthScripts: [],
  staleDays: 180,
  compatMonths: 12,
};

export interface AuditResult {
  generatedAt: string;
  findings: Finding[];
  gaps: CoverageGap[];
  summary: Record<Severity, number>;
  accounts: { id: string; name: string; scripts: number; zones: number }[];
  localFiles: number;
}
