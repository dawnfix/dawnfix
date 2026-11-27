// API tokens: write access to every account or zone, no expiry, or unused for months.

import { daysBetween } from '../hosts.js';
import type { CfToken, Finding } from '../types.js';
import { label, type Ctx } from './context.js';

const WRITE = /\b(write|edit|admin)\b/i;
const ALL_RESOURCES = /^com\.cloudflare\.api\.(account|user)\.\*$|^com\.cloudflare\.api\.account\.zone\.\*$/;
export const BROAD_WRITE_GROUPS = 8;
const UNUSED_DAYS = 90;

export function tokenIssues(t: CfToken, now: Date): Omit<Finding, 'account' | 'source'>[] {
  const out: Omit<Finding, 'account' | 'source'>[] = [];
  if (t.status && t.status !== 'active') return out;
  const resource = `${t.name} (${t.scope} token)`;
  const writes = t.policies.filter((p) => p.effect === 'allow').flatMap((p) => p.permissionGroups.filter((g) => WRITE.test(g)).map((g) => ({ g, p })));
  const everywhere = writes.filter(({ p }) => p.resources.some((r) => ALL_RESOURCES.test(r)));
  const uniqueWrites = [...new Set(writes.map((w) => w.g))];
  if (everywhere.length > 0) {
    const groups = [...new Set(everywhere.map((w) => w.g))];
    out.push({
      check: 'token-over-scoped',
      severity: 'high',
      resource,
      title: 'Write access on all accounts or all zones',
      detail: `${groups.slice(0, 6).join(', ')}${groups.length > 6 ? ` and ${groups.length - 6} more` : ''} on every ${everywhere.some(({ p }) => p.resources.some((r) => r.includes('zone'))) ? 'zone' : 'account'}.${t.ipRestricted ? '' : ' No client IP restriction.'}`,
      fix: 'Roll a replacement scoped to the one account and the zones it needs, then delete this one.',
    });
  } else if (uniqueWrites.length >= BROAD_WRITE_GROUPS) {
    out.push({
      check: 'token-over-scoped',
      severity: 'medium',
      resource,
      title: `${uniqueWrites.length} write permission groups`,
      detail: `${uniqueWrites.slice(0, 6).join(', ')}, ... A token this broad is usually several jobs sharing one secret.`,
      fix: 'Split it into one token per job, each with only what that job writes.',
    });
  }
  if (!t.expiresOn) {
    out.push({
      check: 'token-no-expiry',
      severity: writes.length ? 'medium' : 'low',
      resource,
      title: 'Never expires',
      detail: `Issued ${t.issuedOn?.slice(0, 10) ?? 'on an unknown date'}${writes.length ? ', with write access' : ''}.`,
      fix: 'Set an expiry (Edit token > TTL) and a reminder to roll it.',
    });
  }
  const lastUsed = t.lastUsedOn ? daysBetween(new Date(t.lastUsedOn), now) : undefined;
  if (lastUsed !== undefined && lastUsed > UNUSED_DAYS) {
    out.push({
      check: 'token-unused',
      severity: 'low',
      resource,
      title: `Unused for ${lastUsed} days`,
      detail: `Last used ${t.lastUsedOn!.slice(0, 10)}.`,
      fix: 'Delete it if nothing needs it.',
    });
  }
  return out;
}

export function checkTokens(ctx: Ctx): Finding[] {
  const seen = new Set<string>();
  const out: Finding[] = [];
  for (const a of ctx.accounts) {
    for (const t of a.snap.tokens ?? []) {
      if (seen.has(t.id)) continue;
      seen.add(t.id);
      for (const f of tokenIssues(t, ctx.opts.now)) out.push({ ...f, account: t.scope === 'user' ? 'user' : label(a.snap), source: 'api' });
    }
  }
  return out;
}
