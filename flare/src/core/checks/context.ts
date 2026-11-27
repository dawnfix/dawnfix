// Indexes built once per audit so each check is a short loop over plain data.

import { hostOf } from '../hosts.js';
import type { AccountSnapshot, AuditOptions, LocalWorker, Snapshot } from '../types.js';

export interface AccountView {
  snap: AccountSnapshot;
  scriptNames: Set<string>;
  /** Hostnames each script answers on, from custom domains and zone routes. */
  hostsByScript: Map<string, Set<string>>;
  /** Local wrangler records whose name matches a script in this account. */
  local: Map<string, LocalWorker>;
}

export interface Ctx {
  snap: Snapshot;
  opts: AuditOptions;
  accounts: AccountView[];
  /** Local workers that matched no script in any account. */
  unmatchedLocal: LocalWorker[];
}

export function buildContext(snap: Snapshot, opts: AuditOptions): Ctx {
  const matched = new Set<LocalWorker>();
  const accounts = snap.accounts.map((a): AccountView => {
    const scriptNames = new Set((a.scripts ?? []).map((s) => s.name));
    const hostsByScript = new Map<string, Set<string>>();
    const add = (script: string, host: string) => {
      if (!hostsByScript.has(script)) hostsByScript.set(script, new Set());
      hostsByScript.get(script)!.add(host);
    };
    for (const d of a.customDomains ?? []) add(d.service, d.hostname.toLowerCase());
    for (const z of a.zones ?? []) for (const r of z.routes ?? []) if (r.script) add(r.script, hostOf(r.pattern));
    for (const s of a.scripts ?? []) for (const p of s.routes) add(s.name, hostOf(p));
    const local = new Map<string, LocalWorker>();
    for (const w of snap.local) {
      if (scriptNames.has(w.name)) {
        local.set(w.name, w);
        matched.add(w);
      }
    }
    return { snap: a, scriptNames, hostsByScript, local };
  });
  return { snap, opts, accounts, unmatchedLocal: snap.local.filter((w) => !matched.has(w)) };
}

export const label = (a: AccountSnapshot) => a.name || a.id;
