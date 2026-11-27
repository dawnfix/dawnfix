// Scripts nobody can reach or nobody has touched, old compatibility dates, and secret
// names that changed since the last run (names only: values are never read or kept).

import { daysBetween, monthsBetween } from '../hosts.js';
import type { Finding } from '../types.js';
import { label, type Ctx } from './context.js';

const NON_HTTP_ENTRY = ['queue', 'email', 'tail', 'alarm'];

export function checkDeadScripts(ctx: Ctx): Finding[] {
  const out: Finding[] = [];
  for (const a of ctx.accounts) {
    const scripts = a.snap.scripts ?? [];
    // Only call a script unreachable when every way in was readable.
    const complete = a.snap.zones !== undefined && a.snap.customDomains !== undefined && (a.snap.zones ?? []).every((z) => z.routes !== undefined);
    const bound = new Set(scripts.flatMap((s) => (s.bindings ?? []).filter((b) => b.type === 'service' && b.service).map((b) => b.service!)));
    for (const s of scripts) {
      const reasons: string[] = [];
      const hosts = a.hostsByScript.get(s.name)?.size ?? 0;
      const hasCron = (s.crons?.length ?? 0) > 0 || (s.crons === undefined && s.handlers.includes('scheduled'));
      const otherEntry = s.handlers.some((h) => NON_HTTP_ENTRY.includes(h));
      const reachable = hosts > 0 || s.subdomain?.enabled === true || hasCron || otherEntry || bound.has(s.name);
      if (complete && s.subdomain !== undefined && !reachable) {
        reasons.push('no route, no custom domain, workers.dev off, no cron or queue/email handler, and no service binding points at it');
      }
      const last = s.lastDeployedOn ?? s.modifiedOn;
      const age = last ? daysBetween(new Date(last), ctx.opts.now) : undefined;
      if (age !== undefined && age > ctx.opts.staleDays) reasons.push(`last deployed ${age} days ago (${last!.slice(0, 10)})`);
      if (reasons.length === 0) continue;
      const unreachable = reasons.length === 2 || reasons[0]!.startsWith('no route');
      out.push({
        check: 'dead-script',
        severity: reasons.length === 2 ? 'medium' : 'low',
        account: label(a.snap),
        resource: s.name,
        title: reasons.length === 2 ? 'Unreachable and not deployed for a long time' : unreachable ? 'Unreachable script' : `Not deployed for ${age} days`,
        detail: `${reasons.join('; ')}. Old scripts keep their secrets and bindings live.`,
        fix: unreachable ? `If nothing uses it: wrangler delete --name ${s.name}. Otherwise note why it is kept.` : 'Redeploy to pick up runtime fixes, or delete it if retired.',
        source: 'api',
      });
    }
  }
  return out;
}

export function checkCompatDates(ctx: Ctx): Finding[] {
  const out: Finding[] = [];
  const limit = ctx.opts.compatMonths;
  const seen = new Set<string>();
  const make = (account: string, resource: string, date: string, where: string, source: Finding['source']): Finding | undefined => {
    const d = new Date(`${date}T00:00:00Z`);
    if (Number.isNaN(d.getTime())) return undefined;
    const months = monthsBetween(d, ctx.opts.now);
    if (months < limit) return undefined;
    return {
      check: 'compat-date-old',
      severity: months >= limit * 2 ? 'medium' : 'low',
      account,
      resource,
      title: `compatibility_date is ${months} months old`,
      detail: `${date}${where}. Runtime behaviour fixes after that date are off for this Worker.`,
      fix: 'Read the compatibility flags changelog for the dates in between, raise compatibility_date, run the tests, redeploy.',
      source,
    };
  };
  for (const a of ctx.accounts) {
    for (const s of a.snap.scripts ?? []) {
      if (!s.compatibilityDate) continue;
      const lw = a.local.get(s.name);
      const f = make(label(a.snap), s.name, s.compatibilityDate, lw ? ` (deployed; ${lw.file} has ${lw.compatibilityDate ?? 'none'})` : ' (deployed)', lw ? 'api+local' : 'api');
      if (f) out.push(f);
      seen.add(s.name);
    }
  }
  for (const w of ctx.snap.local) {
    if (seen.has(w.name) || !w.compatibilityDate) continue;
    const f = make('local', w.name, w.compatibilityDate, ` in ${w.file}`, 'local');
    if (f) out.push(f);
  }
  return out;
}

/** Returns findings and the baseline to keep for the next run. */
export function checkSecrets(ctx: Ctx): { findings: Finding[]; baseline: Record<string, string[]> } {
  const findings: Finding[] = [];
  const baseline: Record<string, string[]> = {};
  const prev = ctx.opts.secretsBaseline;
  for (const a of ctx.accounts) {
    for (const s of a.snap.scripts ?? []) {
      if (!s.secretNames) continue;
      const key = `${a.snap.id}/${s.name}`;
      baseline[key] = [...s.secretNames];
      const before = prev?.[key];
      if (!before) continue;
      const added = s.secretNames.filter((n) => !before.includes(n));
      const removed = before.filter((n) => !s.secretNames!.includes(n));
      if (added.length === 0 && removed.length === 0) continue;
      findings.push({
        check: 'secrets-changed',
        severity: removed.length ? 'medium' : 'low',
        account: label(a.snap),
        resource: s.name,
        title: `Secrets changed: ${s.secretNames.length} now, ${before.length} before`,
        detail: [added.length ? `added ${added.join(', ')}` : '', removed.length ? `removed ${removed.join(', ')}` : ''].filter(Boolean).join('; ') + '. Names only; values are never read.',
        fix: 'Confirm the change was yours (wrangler secret list). A removed secret often breaks the next request that needs it.',
        source: 'api',
      });
    }
  }
  // Keep entries for scripts this run could not read, so a gap does not erase history.
  for (const [k, v] of Object.entries(prev ?? {})) if (!(k in baseline)) baseline[k] = v;
  return { findings, baseline };
}
