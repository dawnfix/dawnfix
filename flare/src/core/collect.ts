// Reads one token's accounts into a Snapshot. Every endpoint that fails becomes a
// CoverageGap instead of an exception: a token without Access Read still gets the rest of
// the audit, and the report says which checks did not run and why.

import { CfApiError, type CfClient } from './client.js';
import type {
  AccountSnapshot,
  CfAccessApp,
  CfBinding,
  CfCustomDomain,
  CfDnsRecord,
  CfRoute,
  CfScript,
  CfToken,
  CfTokenPolicy,
  CfZone,
  CfZoneSettings,
  CoverageGap,
} from './types.js';

/* eslint-disable @typescript-eslint/no-explicit-any */
type Raw = Record<string, any>;

export interface CollectOptions {
  /** Limit to these account ids; otherwise every account the token can see. */
  accountIds?: string[];
  /** Skip the per-script calls (subdomain, settings, secrets, deployments). */
  shallow?: boolean;
}

export function describeError(e: unknown): string {
  if (e instanceof CfApiError) return e.isPermission ? `token lacks the scope (HTTP ${e.status})` : `HTTP ${e.status}: ${e.message}`;
  return e instanceof Error ? e.message : String(e);
}

/** Runs fn; on failure records one gap per (account, what) and returns undefined. */
async function attempt<T>(gaps: CoverageGap[], account: string, what: string, fn: () => Promise<T>): Promise<T | undefined> {
  try {
    return await fn();
  } catch (e) {
    const r = describeError(e);
    const existing = gaps.find((g) => g.account === account && g.what === what);
    if (existing) {
      const m = /\((\d+) items\)$/.exec(existing.reason);
      const n = m ? Number(m[1]) + 1 : 2;
      existing.reason = `${existing.reason.replace(/ \(\d+ items\)$/, '')} (${n} items)`;
    } else gaps.push({ account, what, reason: r });
    return undefined;
  }
}

export function mapBinding(b: Raw): CfBinding {
  return {
    type: String(b.type ?? ''),
    name: String(b.name ?? ''),
    ...(b.namespace_id !== undefined ? { namespaceId: String(b.namespace_id) } : {}),
    ...(b.type === 'service' && b.service ? { service: String(b.service) } : {}),
  };
}

export function mapToken(t: Raw, scope: 'user' | 'account'): CfToken {
  const policies: CfTokenPolicy[] = (Array.isArray(t.policies) ? t.policies : []).map((p: Raw) => {
    const groups: Raw[] = Array.isArray(p.permission_groups) ? p.permission_groups : [];
    const ids = groups.filter((g) => g.id !== undefined).map((g) => String(g.id));
    return {
      effect: p.effect === 'deny' ? 'deny' : 'allow',
      // A group listed by id only keeps its id here until resolveGroupNames finds the name.
      permissionGroups: groups.map((g) => String(g.name ?? g.id ?? '')),
      ...(ids.length ? { permissionGroupIds: ids } : {}),
      resources: flattenResources(p.resources),
    };
  });
  const cond = t.condition?.request_ip;
  return {
    id: String(t.id),
    name: String(t.name ?? t.id),
    ...(t.status ? { status: String(t.status) } : {}),
    ...(t.expires_on ? { expiresOn: String(t.expires_on) } : {}),
    ...(t.last_used_on ? { lastUsedOn: String(t.last_used_on) } : {}),
    ...(t.issued_on ? { issuedOn: String(t.issued_on) } : {}),
    ipRestricted: Boolean(cond && ((cond.in?.length ?? 0) > 0 || (cond.not_in?.length ?? 0) > 0)),
    policies,
    scope,
  };
}

/** resources is { key: "*" } or { key: { nestedKey: "*" } }; keep every key, nested included. */
function flattenResources(r: unknown): string[] {
  if (!r || typeof r !== 'object') return [];
  const out: string[] = [];
  for (const [k, v] of Object.entries(r as Raw)) {
    out.push(k);
    if (v && typeof v === 'object') out.push(...flattenResources(v));
  }
  return out;
}

/** Groups that came back as ids only (no name), across the tokens given. */
export function unnamedGroupIds(tokens: CfToken[]): string[] {
  const out = new Set<string>();
  for (const t of tokens) for (const p of t.policies) for (const id of p.permissionGroupIds ?? []) if (p.permissionGroups.includes(id)) out.add(id);
  return [...out];
}

/** Replaces group ids with names from the permission-groups list (GET .../tokens/permission_groups). */
export function resolveGroupNames(tokens: CfToken[], names: Map<string, string>): void {
  for (const t of tokens) for (const p of t.policies) p.permissionGroups = p.permissionGroups.map((g) => names.get(g) ?? g);
}

export function mapAccessApp(a: Raw): CfAccessApp {
  const domains = new Set<string>();
  const workers = new Set<string>();
  let allWorkers = false;
  if (typeof a.domain === 'string' && a.domain) domains.add(a.domain);
  for (const d of Array.isArray(a.self_hosted_domains) ? a.self_hosted_domains : []) if (typeof d === 'string') domains.add(d);
  for (const d of Array.isArray(a.destinations) ? a.destinations : []) {
    if (d && d.type === 'public' && typeof d.uri === 'string') domains.add(d.uri);
    // Unverified against the live API: the field naming the script is not documented in what
    // this was built from, so the likely spellings are all read.
    if (d && d.type === 'worker') {
      const name = d.script_name ?? d.worker_name ?? d.script ?? d.name;
      if (typeof name === 'string' && name) workers.add(name);
    }
    if (d && d.type === 'all_workers') allWorkers = true;
  }
  return {
    id: a.id,
    name: a.name,
    type: a.type,
    domains: [...domains],
    ...(workers.size ? { workers: [...workers] } : {}),
    ...(allWorkers ? { allWorkers } : {}),
  };
}

export async function collectToken(client: CfClient, opts: CollectOptions = {}): Promise<AccountSnapshot[]> {
  let accounts: { id: string; name: string }[];
  if (opts.accountIds?.length) {
    accounts = await Promise.all(
      opts.accountIds.map(async (id) => {
        try {
          const env = await client.get<Raw>(`/accounts/${id}`);
          return { id, name: String(env.result?.name ?? id) };
        } catch {
          return { id, name: id };
        }
      }),
    );
  } else {
    const raw = await client.getAll<Raw>('/accounts', {}, 50);
    accounts = raw.map((a) => ({ id: String(a.id), name: String(a.name ?? a.id) }));
  }

  const snaps = await Promise.all(accounts.map((a) => collectAccount(client, a, opts)));

  // User-owned tokens belong to the person, not an account; attach them to the first one.
  const first = snaps[0];
  if (first) {
    const userTokens = await attempt(first.gaps, first.name, 'user API tokens', async () =>
      (await client.getAll<Raw>('/user/tokens', {}, 50)).map((t) => mapToken(t, 'user')),
    );
    if (userTokens) {
      const ids = unnamedGroupIds(userTokens);
      if (ids.length) {
        const list = await attempt(first.gaps, first.name, 'permission group names (user)', () => client.get<Raw[]>('/user/tokens/permission_groups'));
        if (list) resolveGroupNames(userTokens, new Map((list.result ?? []).map((g) => [String(g.id), String(g.name ?? g.id)])));
      }
      first.tokens = [...(first.tokens ?? []), ...userTokens];
    }
  }
  return snaps;
}

async function collectAccount(client: CfClient, acct: { id: string; name: string }, opts: CollectOptions): Promise<AccountSnapshot> {
  const gaps: CoverageGap[] = [];
  const A = acct.name;
  const base = `/accounts/${acct.id}`;
  const snap: AccountSnapshot = { id: acct.id, name: acct.name, gaps };

  const [sub, scriptsRaw, domainsRaw, zonesRaw, appsRaw, tokensRaw] = await Promise.all([
    attempt(gaps, A, 'workers.dev subdomain', () => client.get<Raw>(`${base}/workers/subdomain`)),
    attempt(gaps, A, 'Workers scripts', () => client.get<Raw[]>(`${base}/workers/scripts`)),
    attempt(gaps, A, 'Workers custom domains', () => client.get<Raw[]>(`${base}/workers/domains`)),
    attempt(gaps, A, 'zones', () => client.getAll<Raw>('/zones', { 'account.id': acct.id }, 50)),
    attempt(gaps, A, 'Access applications', () => client.getAll<Raw>(`${base}/access/apps`, {}, 1000)),
    attempt(gaps, A, 'account API tokens', () => client.getAll<Raw>(`${base}/tokens`, {}, 50)),
  ]);

  if (sub?.result?.subdomain) snap.workersSubdomain = String(sub.result.subdomain);

  if (scriptsRaw) {
    snap.scripts = await Promise.all(
      (scriptsRaw.result ?? []).map(async (s): Promise<CfScript> => {
        const name = String(s.id);
        const script: CfScript = {
          name,
          ...(s.created_on ? { createdOn: String(s.created_on) } : {}),
          ...(s.modified_on ? { modifiedOn: String(s.modified_on) } : {}),
          ...(s.compatibility_date ? { compatibilityDate: String(s.compatibility_date) } : {}),
          handlers: Array.isArray(s.handlers) ? s.handlers.map(String) : [],
          routes: (Array.isArray(s.routes) ? s.routes : []).map((r: Raw) => String(r.pattern)),
        };
        if (opts.shallow) return script;
        const enc = encodeURIComponent(name);
        const [sd, settings, secrets, deps, sched] = await Promise.all([
          attempt(gaps, A, 'per-script workers.dev / preview flags', () => client.get<Raw>(`${base}/workers/scripts/${enc}/subdomain`)),
          attempt(gaps, A, 'per-script bindings', () => client.get<Raw>(`${base}/workers/scripts/${enc}/settings`)),
          attempt(gaps, A, 'per-script secret names', () => client.get<Raw[]>(`${base}/workers/scripts/${enc}/secrets`)),
          attempt(gaps, A, 'per-script deployments', () => client.get<Raw>(`${base}/workers/scripts/${enc}/deployments`)),
          s.handlers?.includes?.('scheduled')
            ? attempt(gaps, A, 'per-script cron schedules', () => client.get<Raw>(`${base}/workers/scripts/${enc}/schedules`))
            : Promise.resolve(undefined),
        ]);
        if (sched?.result) script.crons = (Array.isArray(sched.result.schedules) ? sched.result.schedules : []).map((x: Raw) => String(x.cron));
        if (sd?.result) script.subdomain = { enabled: Boolean(sd.result.enabled), previewsEnabled: Boolean(sd.result.previews_enabled) };
        if (settings?.result) {
          script.bindings = (Array.isArray(settings.result.bindings) ? settings.result.bindings : []).map(mapBinding);
          if (!script.compatibilityDate && settings.result.compatibility_date) script.compatibilityDate = String(settings.result.compatibility_date);
        }
        // Names only. The API can return a secret's text; it is never copied out of here.
        if (secrets?.result) script.secretNames = secrets.result.map((x) => String(x.name)).sort();
        const latest = deps?.result?.deployments?.[0];
        if (latest?.created_on) script.lastDeployedOn = String(latest.created_on);
        return script;
      }),
    );
  }

  if (domainsRaw) {
    snap.customDomains = (domainsRaw.result ?? []).map(
      (d): CfCustomDomain => ({
        hostname: String(d.hostname),
        service: String(d.service),
        ...(d.zone_id ? { zoneId: String(d.zone_id) } : {}),
        ...(d.zone_name ? { zoneName: String(d.zone_name) } : {}),
      }),
    );
  }

  if (zonesRaw) {
    snap.zones = await Promise.all(
      zonesRaw.map(async (z): Promise<CfZone> => {
        const zid = String(z.id);
        const zone: CfZone = { id: zid, name: String(z.name), ...(z.status ? { status: String(z.status) } : {}) };
        const zb = `/zones/${zid}`;
        const [routes, dns, tls, https, hsts] = await Promise.all([
          attempt(gaps, A, 'zone Workers routes', () => client.get<Raw[]>(`${zb}/workers/routes`)),
          attempt(gaps, A, 'zone DNS records', () => client.getAll<Raw>(`${zb}/dns_records`, {}, 1000)),
          attempt(gaps, A, 'zone setting min_tls_version', () => client.get<Raw>(`${zb}/settings/min_tls_version`)),
          attempt(gaps, A, 'zone setting always_use_https', () => client.get<Raw>(`${zb}/settings/always_use_https`)),
          attempt(gaps, A, 'zone setting security_header', () => client.get<Raw>(`${zb}/settings/security_header`)),
        ]);
        if (routes) zone.routes = (routes.result ?? []).map((r): CfRoute => ({ id: String(r.id), pattern: String(r.pattern), ...(r.script ? { script: String(r.script) } : {}) }));
        if (dns) zone.dns = dns.map((r): CfDnsRecord => ({ id: String(r.id), type: String(r.type), name: String(r.name), content: String(r.content ?? ''), ...(r.proxied !== undefined ? { proxied: Boolean(r.proxied) } : {}) }));
        const settings: CfZoneSettings = {};
        if (tls?.result?.value !== undefined) settings.minTlsVersion = String(tls.result.value);
        if (https?.result?.value !== undefined) settings.alwaysUseHttps = String(https.result.value);
        const sts = hsts?.result?.value?.strict_transport_security;
        if (hsts?.result) settings.hsts = { enabled: Boolean(sts?.enabled), maxAge: Number(sts?.max_age ?? 0), includeSubdomains: Boolean(sts?.include_subdomains) };
        if (tls || https || hsts) zone.settings = settings;
        return zone;
      }),
    );
  }

  if (appsRaw) snap.accessApps = appsRaw.map(mapAccessApp);
  if (tokensRaw) {
    snap.tokens = tokensRaw.map((t) => mapToken(t, 'account'));
    if (unnamedGroupIds(snap.tokens).length) {
      const list = await attempt(gaps, A, 'permission group names', () => client.get<Raw[]>(`${base}/tokens/permission_groups`));
      if (list) resolveGroupNames(snap.tokens, new Map((list.result ?? []).map((g) => [String(g.id), String(g.name ?? g.id)])));
    }
  }
  return snap;
}
