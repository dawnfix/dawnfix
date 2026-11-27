// A ratelimit namespace_id is account-wide: every binding naming it shares the counters,
// across Workers. Two Workers on one id means one site's visitors spend the other's limit.

import type { Finding } from '../types.js';
import { label, type Ctx } from './context.js';

interface Use {
  worker: string;
  binding: string;
  from: 'api' | 'local';
  file?: string;
}

/** The first id of the next free hundred-block above every numeric id in use. */
export function nextFreeBlock(ids: string[]): string | undefined {
  const nums = ids.map(Number).filter((n) => Number.isInteger(n) && n >= 0);
  if (nums.length === 0) return undefined;
  return String((Math.floor(Math.max(...nums) / 100) + 1) * 100 + 1);
}

function findingsFor(pool: Map<string, Use[]>, account: string): Finding[] {
  const out: Finding[] = [];
  const free = nextFreeBlock([...pool.keys()]);
  for (const [id, uses] of [...pool].sort(([a], [b]) => a.localeCompare(b, 'en', { numeric: true }))) {
    // The same binding seen from the API and a local file is one use, not two.
    const unique = new Map<string, Use>();
    for (const u of uses) {
      const k = `${u.worker}\u0000${u.binding}`;
      const prev = unique.get(k);
      unique.set(k, prev && prev.from !== u.from ? { ...prev, from: 'api', file: prev.file ?? u.file } : (prev ?? u));
    }
    const list = [...unique.values()];
    const workers = [...new Set(list.map((u) => u.worker))].sort();
    const sources = new Set(uses.map((u) => u.from));
    const source = sources.size === 2 ? 'api+local' : sources.has('api') ? 'api' : 'local';
    const where = list.map((u) => `${u.worker}.${u.binding}${u.file ? ` (${u.file})` : ''}`).join(', ');
    if (workers.length > 1) {
      out.push({
        check: 'ratelimit-namespace-shared',
        severity: 'high',
        account,
        resource: `namespace ${id}`,
        title: `Rate-limit namespace ${id} shared by ${workers.length} Workers`,
        detail: `${where}. They share counters, so traffic to one spends the others' limit.`,
        fix: `Give each Worker its own ids${free ? ` (next free block: ${free}-${Number(free) + 98})` : ''} and redeploy each.`,
        source,
      });
    } else if (list.length > 1) {
      out.push({
        check: 'ratelimit-namespace-shared',
        severity: 'medium',
        account,
        resource: `namespace ${id}`,
        title: `Two limits in ${workers[0]} share namespace ${id}`,
        detail: `${where}. Both bindings count against the same counters, so neither limit holds as written.`,
        fix: `Give each binding its own namespace_id${free ? ` (next free block: ${free})` : ''}.`,
        source,
      });
    }
  }
  return out;
}

export function checkRatelimitNamespaces(ctx: Ctx): Finding[] {
  const out: Finding[] = [];
  const add = (pool: Map<string, Use[]>, id: string, u: Use) => {
    if (!pool.has(id)) pool.set(id, []);
    pool.get(id)!.push(u);
  };
  // With exactly one account, local files that match no script are assumed to deploy there.
  const single = ctx.accounts.length === 1;
  for (const a of ctx.accounts) {
    const pool = new Map<string, Use[]>();
    for (const s of a.snap.scripts ?? []) {
      for (const b of s.bindings ?? []) if (b.type === 'ratelimit' && b.namespaceId) add(pool, b.namespaceId, { worker: s.name, binding: b.name, from: 'api' });
    }
    const locals = [...a.local.values(), ...(single ? ctx.unmatchedLocal : [])];
    for (const w of locals) for (const r of w.ratelimitNamespaces) add(pool, r.namespaceId, { worker: w.name, binding: r.binding, from: 'local', file: w.file });
    out.push(...findingsFor(pool, label(a.snap)));
  }
  if (!single) {
    const pool = new Map<string, Use[]>();
    for (const w of ctx.unmatchedLocal) for (const r of w.ratelimitNamespaces) add(pool, r.namespaceId, { worker: w.name, binding: r.binding, from: 'local', file: w.file });
    out.push(...findingsFor(pool, 'local'));
  }
  return out;
}
