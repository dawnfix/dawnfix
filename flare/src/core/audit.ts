// Runs every check over a Snapshot. Pure: same snapshot and options, same result, so
// recorded snapshots are the test fixtures and a Worker can run this on a cron.

import { CfClient, type FetchLike } from './client.js';
import { collectToken, describeError, type CollectOptions } from './collect.js';
import { buildContext } from './checks/context.js';
import { checkHostnameAuth, checkWorkersDev } from './checks/exposure.js';
import { checkCompatDates, checkDeadScripts, checkSecrets } from './checks/lifecycle.js';
import { checkRatelimitNamespaces } from './checks/ratelimit.js';
import { checkDanglingDns, checkRoutesToMissingScripts } from './checks/routing.js';
import { checkTokens } from './checks/tokens.js';
import { checkZoneTls } from './checks/zones.js';
import { SEVERITIES, severityRank, type AccountSnapshot, type AuditOptions, type AuditResult, type LocalWorker, type Severity, type Snapshot } from './types.js';

export function audit(snap: Snapshot, opts: AuditOptions): { result: AuditResult; secretsBaseline: Record<string, string[]> } {
  const ctx = buildContext(snap, opts);
  const secrets = checkSecrets(ctx);
  const findings = [
    ...checkWorkersDev(ctx),
    ...checkHostnameAuth(ctx),
    ...checkRatelimitNamespaces(ctx),
    ...checkRoutesToMissingScripts(ctx),
    ...checkDanglingDns(ctx),
    ...checkDeadScripts(ctx),
    ...checkCompatDates(ctx),
    ...secrets.findings,
    ...checkTokens(ctx),
    ...checkZoneTls(ctx),
  ].sort((a, b) => severityRank(b.severity) - severityRank(a.severity) || a.check.localeCompare(b.check) || a.account.localeCompare(b.account) || a.resource.localeCompare(b.resource));

  const summary = Object.fromEntries(SEVERITIES.map((s) => [s, 0])) as Record<Severity, number>;
  for (const f of findings) summary[f.severity]++;

  return {
    result: {
      generatedAt: opts.now.toISOString(),
      findings,
      gaps: [...snap.accounts.flatMap((a) => a.gaps), ...snap.localGaps],
      summary,
      accounts: snap.accounts.map((a) => ({ id: a.id, name: a.name, scripts: a.scripts?.length ?? 0, zones: a.zones?.length ?? 0 })),
      localFiles: new Set(snap.local.map((w) => w.file)).size,
    },
    secretsBaseline: secrets.baseline,
  };
}

/** Collects every token's accounts. Tokens seeing the same account are merged, first wins. */
export async function collectSnapshot(input: {
  tokens: string[];
  fetch: FetchLike;
  local?: LocalWorker[];
  collect?: CollectOptions;
  now: Date;
  concurrency?: number;
}): Promise<{ snapshot: Snapshot; calls: string[] }> {
  const accounts: AccountSnapshot[] = [];
  const calls: string[] = [];
  const localGaps: Snapshot['localGaps'] = [];
  for (const [i, token] of input.tokens.entries()) {
    const client = new CfClient({ token, fetch: input.fetch, ...(input.concurrency ? { concurrency: input.concurrency } : {}) });
    try {
      for (const a of await collectToken(client, input.collect)) if (!accounts.some((x) => x.id === a.id)) accounts.push(a);
    } catch (e) {
      localGaps.push({ account: `token #${i + 1}`, what: 'account list', reason: describeError(e) });
    }
    calls.push(...client.calls);
  }
  return { snapshot: { takenAt: input.now.toISOString(), accounts, local: input.local ?? [], localGaps }, calls };
}

/** Exit status for CI: 1 when any finding is at or above the threshold. */
export function failsAt(result: AuditResult, threshold: Severity | 'never'): boolean {
  if (threshold === 'never') return false;
  return result.findings.some((f) => severityRank(f.severity) >= severityRank(threshold));
}
