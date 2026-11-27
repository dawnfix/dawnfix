// The one document a CI run sends to the hosted service, only with an Enterprise key: `dawnfix.flare/1`
// (schema/flare-ingest.schema.json). Counts per check and severity, how many accounts were
// audited and a salted hash of each account id. No hostname, script, zone, token or secret
// name, no account name: those stay in the run's job summary in the customer's GitHub.
// Runtime-neutral (WebCrypto), so a Worker could build it too.

import { CHECK_IDS, SEVERITIES, type AuditResult, type CheckId, type Severity } from './types.js';

export const INGEST_SCHEMA = 'dawnfix.flare/1';
/** More accounts than this in one run is refused: split the audit across workflows. */
export const MAX_INGEST_ACCOUNTS = 100;
/** Fixed salt: the hash is an id that groups runs of one account, not a secret. */
const ACCOUNT_SALT = 'dawnfix.flare/1:account:';

export type SeverityCounts = Record<Severity, number>;

export interface FlareIngest {
  schema: typeof INGEST_SCHEMA;
  /** UTC, to the second. */
  generated_at: string;
  /** Cloudflare accounts audited in this run. */
  accounts: number;
  /** 16 hex of SHA-256 over a fixed salt and each account id, sorted. */
  account_ids: string[];
  /** wrangler files read from the repo. */
  local_files: number;
  /** Parts of an account the token could not read (their checks did not run). */
  gaps: number;
  summary: SeverityCounts;
  findings: Record<CheckId, SeverityCounts>;
}

const zero = (): SeverityCounts => Object.fromEntries(SEVERITIES.map((s) => [s, 0])) as SeverityCounts;

export async function hashAccountId(id: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(ACCOUNT_SALT + id));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('').slice(0, 16);
}

export async function ingestDoc(result: AuditResult): Promise<FlareIngest> {
  if (result.accounts.length > MAX_INGEST_ACCOUNTS) {
    throw new Error(`${result.accounts.length} accounts in one run; the ingest takes at most ${MAX_INGEST_ACCOUNTS}`);
  }
  const findings = Object.fromEntries(CHECK_IDS.map((c) => [c, zero()])) as Record<CheckId, SeverityCounts>;
  const summary = zero();
  for (const f of result.findings) {
    findings[f.check][f.severity]++;
    summary[f.severity]++;
  }
  const ids = [...new Set(await Promise.all(result.accounts.map((a) => hashAccountId(a.id))))].sort();
  return {
    schema: INGEST_SCHEMA,
    generated_at: `${result.generatedAt.slice(0, 19)}Z`,
    accounts: ids.length,
    account_ids: ids,
    local_files: result.localFiles,
    gaps: result.gaps.length,
    summary,
    findings,
  };
}
