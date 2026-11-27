#!/usr/bin/env node
// Dawnfix Flare: read-only audit of Cloudflare accounts and Workers.
// Source available under FSL-1.1-ALv2 (see LICENSE at the repo root).
// GENERATED from src/ by `npm run build` (esbuild, one file, no dependencies). Do not edit.

// src/cli.ts
import { existsSync as existsSync2, realpathSync } from "node:fs";
import { pathToFileURL } from "node:url";

// src/main.ts
import { existsSync } from "node:fs";
import { appendFile, readFile as readFile4, writeFile as writeFile2 } from "node:fs/promises";
import { homedir as homedir2 } from "node:os";
import { join as join2, resolve as resolve2 } from "node:path";
import { parseArgs } from "node:util";

// src/core/brand.ts
var SITE = "https://dawnfix.dev";
var BRAND = {
  suite: "Dawnfix",
  product: "Flare",
  fullName: "Dawnfix Flare",
  cli: "flare",
  org: "Dawnfix",
  homepage: `${SITE}/flare`,
  docsUrl: `${SITE}/flare#run`,
  checksUrl: `${SITE}/flare#checks`,
  userAgent: "dawnfix-flare/0.1 (read-only audit)",
  /**
   * The closing line of a scan (`--json` carries it as `pitch`): the free daily workflow in
   * the customer's own CI, and the one hosted extra. No prices: Enterprise is "Contact us".
   */
  pitch: {
    line: "Run this audit every day in your own GitHub Actions, free: templates/github/workflows/dawnfix-flare.yml in the Dawnfix repo. Your Cloudflare token stays a GitHub secret. An email the morning a new exposure appears is Dawnfix Enterprise.",
    url: `${SITE}/flare#daily`
  }
};
var CLOUDFLARE_API = "https://api.cloudflare.com/client/v4";

// src/core/client.ts
var CfApiError = class extends Error {
  constructor(path, status, codes, message) {
    super(message);
    this.path = path;
    this.status = status;
    this.codes = codes;
  }
  path;
  status;
  codes;
  /** 403, or 401/400 with the "not authorized" family of codes: the token lacks a scope. */
  get isPermission() {
    return this.status === 403 || this.status === 401 || this.codes.includes(1e4) || this.codes.includes(9109);
  }
};
var CfClient = class {
  constructor(opts) {
    this.opts = opts;
  }
  opts;
  active = 0;
  queue = [];
  calls = [];
  async slot(fn) {
    const limit = this.opts.concurrency ?? 4;
    if (this.active >= limit) await new Promise((r) => this.queue.push(r));
    this.active++;
    try {
      return await fn();
    } finally {
      this.active--;
      this.queue.shift()?.();
    }
  }
  async get(path, query = {}) {
    return this.request("GET", path, query);
  }
  async request(method, path, query = {}) {
    if (method !== "GET") throw new Error(`${BRAND.cli} is read-only: refused ${method} ${path}`);
    const qs = new URLSearchParams(Object.entries(query).map(([k, v]) => [k, String(v)])).toString();
    const base = Object.hasOwn(this.opts, "baseUrl") && this.opts.baseUrl ? this.opts.baseUrl : CLOUDFLARE_API;
    const url = `${base}${path}${qs ? `?${qs}` : ""}`;
    const sleep = this.opts.sleep ?? ((ms) => new Promise((r) => setTimeout(r, ms)));
    return this.slot(async () => {
      for (let attempt2 = 0; ; attempt2++) {
        this.calls.push(`GET ${path}${qs ? `?${qs}` : ""}`);
        const res = await this.opts.fetch(url, {
          method: "GET",
          headers: { authorization: `Bearer ${this.opts.token}`, "user-agent": BRAND.userAgent, accept: "application/json" }
        });
        if ((res.status === 429 || res.status >= 500) && attempt2 < (this.opts.maxRetries ?? 3)) {
          const after = Number(res.headers.get("retry-after"));
          await sleep(Number.isFinite(after) && after > 0 ? Math.min(after, 60) * 1e3 : 500 * 2 ** attempt2);
          continue;
        }
        let body;
        try {
          body = await res.json();
        } catch {
          body = void 0;
        }
        if (res.status >= 400 || !body || body.success === false) {
          const errs = body?.errors ?? [];
          throw new CfApiError(
            path,
            res.status,
            errs.map((e) => e.code),
            errs.map((e) => `${e.code}: ${e.message}`).join("; ") || `HTTP ${res.status}`
          );
        }
        return body;
      }
    });
  }
  /** Follows result_info.total_pages. Endpoints without result_info return their one page. */
  async getAll(path, query = {}, perPage = 100) {
    const out = [];
    for (let page = 1; page <= 1e3; page++) {
      const env = await this.get(path, { ...query, page, per_page: perPage });
      const items = Array.isArray(env.result) ? env.result : [];
      out.push(...items);
      const total = env.result_info?.total_pages;
      if (!total || page >= total || items.length === 0) break;
    }
    return out;
  }
};

// src/core/collect.ts
function describeError(e) {
  if (e instanceof CfApiError) return e.isPermission ? `token lacks the scope (HTTP ${e.status})` : `HTTP ${e.status}: ${e.message}`;
  return e instanceof Error ? e.message : String(e);
}
async function attempt(gaps, account, what, fn) {
  try {
    return await fn();
  } catch (e) {
    const r = describeError(e);
    const existing = gaps.find((g) => g.account === account && g.what === what);
    if (existing) {
      const m = /\((\d+) items\)$/.exec(existing.reason);
      const n = m ? Number(m[1]) + 1 : 2;
      existing.reason = `${existing.reason.replace(/ \(\d+ items\)$/, "")} (${n} items)`;
    } else gaps.push({ account, what, reason: r });
    return void 0;
  }
}
function mapBinding(b) {
  return {
    type: String(b.type ?? ""),
    name: String(b.name ?? ""),
    ...b.namespace_id !== void 0 ? { namespaceId: String(b.namespace_id) } : {},
    ...b.type === "service" && b.service ? { service: String(b.service) } : {}
  };
}
function mapToken(t, scope) {
  const policies = (Array.isArray(t.policies) ? t.policies : []).map((p) => {
    const groups = Array.isArray(p.permission_groups) ? p.permission_groups : [];
    const ids = groups.filter((g) => g.id !== void 0).map((g) => String(g.id));
    return {
      effect: p.effect === "deny" ? "deny" : "allow",
      // A group listed by id only keeps its id here until resolveGroupNames finds the name.
      permissionGroups: groups.map((g) => String(g.name ?? g.id ?? "")),
      ...ids.length ? { permissionGroupIds: ids } : {},
      resources: flattenResources(p.resources)
    };
  });
  const cond = t.condition?.request_ip;
  return {
    id: String(t.id),
    name: String(t.name ?? t.id),
    ...t.status ? { status: String(t.status) } : {},
    ...t.expires_on ? { expiresOn: String(t.expires_on) } : {},
    ...t.last_used_on ? { lastUsedOn: String(t.last_used_on) } : {},
    ...t.issued_on ? { issuedOn: String(t.issued_on) } : {},
    ipRestricted: Boolean(cond && ((cond.in?.length ?? 0) > 0 || (cond.not_in?.length ?? 0) > 0)),
    policies,
    scope
  };
}
function flattenResources(r) {
  if (!r || typeof r !== "object") return [];
  const out = [];
  for (const [k, v] of Object.entries(r)) {
    out.push(k);
    if (v && typeof v === "object") out.push(...flattenResources(v));
  }
  return out;
}
function unnamedGroupIds(tokens) {
  const out = /* @__PURE__ */ new Set();
  for (const t of tokens) for (const p of t.policies) for (const id of p.permissionGroupIds ?? []) if (p.permissionGroups.includes(id)) out.add(id);
  return [...out];
}
function resolveGroupNames(tokens, names) {
  for (const t of tokens) for (const p of t.policies) p.permissionGroups = p.permissionGroups.map((g) => names.get(g) ?? g);
}
function mapAccessApp(a) {
  const domains = /* @__PURE__ */ new Set();
  const workers = /* @__PURE__ */ new Set();
  let allWorkers = false;
  if (typeof a.domain === "string" && a.domain) domains.add(a.domain);
  for (const d of Array.isArray(a.self_hosted_domains) ? a.self_hosted_domains : []) if (typeof d === "string") domains.add(d);
  for (const d of Array.isArray(a.destinations) ? a.destinations : []) {
    if (d && d.type === "public" && typeof d.uri === "string") domains.add(d.uri);
    if (d && d.type === "worker") {
      const name = d.script_name ?? d.worker_name ?? d.script ?? d.name;
      if (typeof name === "string" && name) workers.add(name);
    }
    if (d && d.type === "all_workers") allWorkers = true;
  }
  return {
    id: a.id,
    name: a.name,
    type: a.type,
    domains: [...domains],
    ...workers.size ? { workers: [...workers] } : {},
    ...allWorkers ? { allWorkers } : {}
  };
}
async function collectToken(client, opts = {}) {
  let accounts;
  if (opts.accountIds?.length) {
    accounts = await Promise.all(
      opts.accountIds.map(async (id) => {
        try {
          const env = await client.get(`/accounts/${id}`);
          return { id, name: String(env.result?.name ?? id) };
        } catch {
          return { id, name: id };
        }
      })
    );
  } else {
    const raw = await client.getAll("/accounts", {}, 50);
    accounts = raw.map((a) => ({ id: String(a.id), name: String(a.name ?? a.id) }));
  }
  const snaps = await Promise.all(accounts.map((a) => collectAccount(client, a, opts)));
  const first = snaps[0];
  if (first) {
    const userTokens = await attempt(
      first.gaps,
      first.name,
      "user API tokens",
      async () => (await client.getAll("/user/tokens", {}, 50)).map((t) => mapToken(t, "user"))
    );
    if (userTokens) {
      const ids = unnamedGroupIds(userTokens);
      if (ids.length) {
        const list = await attempt(first.gaps, first.name, "permission group names (user)", () => client.get("/user/tokens/permission_groups"));
        if (list) resolveGroupNames(userTokens, new Map((list.result ?? []).map((g) => [String(g.id), String(g.name ?? g.id)])));
      }
      first.tokens = [...first.tokens ?? [], ...userTokens];
    }
  }
  return snaps;
}
async function collectAccount(client, acct, opts) {
  const gaps = [];
  const A = acct.name;
  const base = `/accounts/${acct.id}`;
  const snap = { id: acct.id, name: acct.name, gaps };
  const [sub, scriptsRaw, domainsRaw, zonesRaw, appsRaw, tokensRaw] = await Promise.all([
    attempt(gaps, A, "workers.dev subdomain", () => client.get(`${base}/workers/subdomain`)),
    attempt(gaps, A, "Workers scripts", () => client.get(`${base}/workers/scripts`)),
    attempt(gaps, A, "Workers custom domains", () => client.get(`${base}/workers/domains`)),
    attempt(gaps, A, "zones", () => client.getAll("/zones", { "account.id": acct.id }, 50)),
    attempt(gaps, A, "Access applications", () => client.getAll(`${base}/access/apps`, {}, 1e3)),
    attempt(gaps, A, "account API tokens", () => client.getAll(`${base}/tokens`, {}, 50))
  ]);
  if (sub?.result?.subdomain) snap.workersSubdomain = String(sub.result.subdomain);
  if (scriptsRaw) {
    snap.scripts = await Promise.all(
      (scriptsRaw.result ?? []).map(async (s) => {
        const name = String(s.id);
        const script = {
          name,
          ...s.created_on ? { createdOn: String(s.created_on) } : {},
          ...s.modified_on ? { modifiedOn: String(s.modified_on) } : {},
          ...s.compatibility_date ? { compatibilityDate: String(s.compatibility_date) } : {},
          handlers: Array.isArray(s.handlers) ? s.handlers.map(String) : [],
          routes: (Array.isArray(s.routes) ? s.routes : []).map((r) => String(r.pattern))
        };
        if (opts.shallow) return script;
        const enc = encodeURIComponent(name);
        const [sd, settings, secrets, deps, sched] = await Promise.all([
          attempt(gaps, A, "per-script workers.dev / preview flags", () => client.get(`${base}/workers/scripts/${enc}/subdomain`)),
          attempt(gaps, A, "per-script bindings", () => client.get(`${base}/workers/scripts/${enc}/settings`)),
          attempt(gaps, A, "per-script secret names", () => client.get(`${base}/workers/scripts/${enc}/secrets`)),
          attempt(gaps, A, "per-script deployments", () => client.get(`${base}/workers/scripts/${enc}/deployments`)),
          s.handlers?.includes?.("scheduled") ? attempt(gaps, A, "per-script cron schedules", () => client.get(`${base}/workers/scripts/${enc}/schedules`)) : Promise.resolve(void 0)
        ]);
        if (sched?.result) script.crons = (Array.isArray(sched.result.schedules) ? sched.result.schedules : []).map((x) => String(x.cron));
        if (sd?.result) script.subdomain = { enabled: Boolean(sd.result.enabled), previewsEnabled: Boolean(sd.result.previews_enabled) };
        if (settings?.result) {
          script.bindings = (Array.isArray(settings.result.bindings) ? settings.result.bindings : []).map(mapBinding);
          if (!script.compatibilityDate && settings.result.compatibility_date) script.compatibilityDate = String(settings.result.compatibility_date);
        }
        if (secrets?.result) script.secretNames = secrets.result.map((x) => String(x.name)).sort();
        const latest = deps?.result?.deployments?.[0];
        if (latest?.created_on) script.lastDeployedOn = String(latest.created_on);
        return script;
      })
    );
  }
  if (domainsRaw) {
    snap.customDomains = (domainsRaw.result ?? []).map(
      (d) => ({
        hostname: String(d.hostname),
        service: String(d.service),
        ...d.zone_id ? { zoneId: String(d.zone_id) } : {},
        ...d.zone_name ? { zoneName: String(d.zone_name) } : {}
      })
    );
  }
  if (zonesRaw) {
    snap.zones = await Promise.all(
      zonesRaw.map(async (z) => {
        const zid = String(z.id);
        const zone = { id: zid, name: String(z.name), ...z.status ? { status: String(z.status) } : {} };
        const zb = `/zones/${zid}`;
        const [routes, dns, tls, https, hsts] = await Promise.all([
          attempt(gaps, A, "zone Workers routes", () => client.get(`${zb}/workers/routes`)),
          attempt(gaps, A, "zone DNS records", () => client.getAll(`${zb}/dns_records`, {}, 1e3)),
          attempt(gaps, A, "zone setting min_tls_version", () => client.get(`${zb}/settings/min_tls_version`)),
          attempt(gaps, A, "zone setting always_use_https", () => client.get(`${zb}/settings/always_use_https`)),
          attempt(gaps, A, "zone setting security_header", () => client.get(`${zb}/settings/security_header`))
        ]);
        if (routes) zone.routes = (routes.result ?? []).map((r) => ({ id: String(r.id), pattern: String(r.pattern), ...r.script ? { script: String(r.script) } : {} }));
        if (dns) zone.dns = dns.map((r) => ({ id: String(r.id), type: String(r.type), name: String(r.name), content: String(r.content ?? ""), ...r.proxied !== void 0 ? { proxied: Boolean(r.proxied) } : {} }));
        const settings = {};
        if (tls?.result?.value !== void 0) settings.minTlsVersion = String(tls.result.value);
        if (https?.result?.value !== void 0) settings.alwaysUseHttps = String(https.result.value);
        const sts = hsts?.result?.value?.strict_transport_security;
        if (hsts?.result) settings.hsts = { enabled: Boolean(sts?.enabled), maxAge: Number(sts?.max_age ?? 0), includeSubdomains: Boolean(sts?.include_subdomains) };
        if (tls || https || hsts) zone.settings = settings;
        return zone;
      })
    );
  }
  if (appsRaw) snap.accessApps = appsRaw.map(mapAccessApp);
  if (tokensRaw) {
    snap.tokens = tokensRaw.map((t) => mapToken(t, "account"));
    if (unnamedGroupIds(snap.tokens).length) {
      const list = await attempt(gaps, A, "permission group names", () => client.get(`${base}/tokens/permission_groups`));
      if (list) resolveGroupNames(snap.tokens, new Map((list.result ?? []).map((g) => [String(g.id), String(g.name ?? g.id)])));
    }
  }
  return snap;
}

// src/core/hosts.ts
function hostOf(pattern) {
  return pattern.replace(/^[a-z]+:\/\//i, "").split("/")[0].toLowerCase().replace(/\.$/, "");
}
function pathOf(pattern) {
  const p = pattern.replace(/^[a-z]+:\/\//i, "");
  const at = p.indexOf("/");
  return at < 0 ? "" : p.slice(at);
}
function hostMatches(rule, host) {
  const r = rule.toLowerCase();
  const h = host.toLowerCase();
  if (r === h || r === "*") return true;
  if (r.startsWith("*.")) return h.endsWith(r.slice(1)) && h.length > r.length - 1;
  if (r.startsWith("*")) return h.endsWith(r.slice(1));
  return false;
}
function accessCoverage(accessDomain, host) {
  if (!hostMatches(hostOf(accessDomain), host)) return "none";
  const path = pathOf(accessDomain);
  return path === "" || path === "/" || path === "/*" ? "full" : "partial";
}
function monthsBetween(from, to) {
  return (to.getUTCFullYear() - from.getUTCFullYear()) * 12 + (to.getUTCMonth() - from.getUTCMonth()) - (to.getUTCDate() < from.getUTCDate() ? 1 : 0);
}
function daysBetween(from, to) {
  return Math.floor((to.getTime() - from.getTime()) / 864e5);
}

// src/core/checks/context.ts
function buildContext(snap, opts) {
  const matched = /* @__PURE__ */ new Set();
  const accounts = snap.accounts.map((a) => {
    const scriptNames = new Set((a.scripts ?? []).map((s) => s.name));
    const hostsByScript = /* @__PURE__ */ new Map();
    const add = (script, host) => {
      if (!hostsByScript.has(script)) hostsByScript.set(script, /* @__PURE__ */ new Set());
      hostsByScript.get(script).add(host);
    };
    for (const d of a.customDomains ?? []) add(d.service, d.hostname.toLowerCase());
    for (const z of a.zones ?? []) for (const r of z.routes ?? []) if (r.script) add(r.script, hostOf(r.pattern));
    for (const s of a.scripts ?? []) for (const p of s.routes) add(s.name, hostOf(p));
    const local = /* @__PURE__ */ new Map();
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
var label = (a) => a.name || a.id;

// src/core/checks/exposure.ts
var WD_FIX = 'Set "workers_dev": false in the wrangler config and redeploy (or Worker > Settings > Domains & Routes > workers.dev > Disable).';
var PV_FIX = 'Set "preview_urls": false in the wrangler config and redeploy (or Worker > Settings > Domains & Routes > Preview URLs > Disable).';
var servesHttp = (handlers) => handlers.length === 0 || handlers.includes("fetch");
function cronOnly(w) {
  if (!w.entry) return false;
  return (w.entry.scheduled || (w.crons?.length ?? 0) > 0) && !w.entry.fetch && !w.entry.opaqueDefault;
}
function effectiveWorkersDev(w) {
  if (w.workersDev !== void 0) return { value: w.workersDev, explicit: true };
  return { value: w.routes.length === 0, explicit: false };
}
function accessOnWorkersDev(apps, script, host) {
  return (apps ?? []).some(
    (app) => app.allWorkers === true || (app.workers ?? []).includes(script) || host !== void 0 && app.domains.some((d) => accessCoverage(d, host) === "full")
  );
}
function checkWorkersDev(ctx) {
  const out = [];
  const reported = /* @__PURE__ */ new Set();
  for (const a of ctx.accounts) {
    for (const s of a.snap.scripts ?? []) {
      const lw = a.local.get(s.name);
      const hosts = a.hostsByScript.get(s.name);
      const sub = a.snap.workersSubdomain;
      const url = sub ? `${s.name}.${sub}.workers.dev` : `${s.name}.<subdomain>.workers.dev`;
      const ACCESS = " An Access application covers it, so a visitor must sign in first.";
      if (s.subdomain?.enabled) {
        reported.add(s.name);
        const hasHosts = (hosts?.size ?? 0) > 0;
        const guarded = accessOnWorkersDev(a.snap.accessApps, s.name, sub ? url : void 0);
        out.push({
          check: "workers-dev-enabled",
          severity: !servesHttp(s.handlers) || guarded ? "low" : hasHosts ? "high" : "medium",
          account: label(a.snap),
          resource: s.name,
          title: (hasHosts ? "Reachable on workers.dev, around its custom domain" : "Public on workers.dev") + (guarded ? " (behind Access)" : ""),
          detail: (hasHosts ? `${url} serves the same Worker as ${[...hosts].join(", ")}, but outside that zone's WAF, rate-limiting rules${guarded ? "" : " and Access"}.` : `${url} is this Worker's only public address; no zone rules apply to it.`) + (guarded ? ACCESS : ""),
          fix: hasHosts ? WD_FIX : `Give it a custom domain, then: ${WD_FIX}`,
          source: lw && !effectiveWorkersDev(lw).explicit ? "api+local" : "api"
        });
      }
      if (s.subdomain?.previewsEnabled) {
        reported.add(`preview:${s.name}`);
        const guarded = accessOnWorkersDev(a.snap.accessApps, s.name, sub ? `00000000-${url}` : void 0);
        out.push({
          check: "preview-urls-enabled",
          severity: servesHttp(s.handlers) && !guarded ? "medium" : "low",
          account: label(a.snap),
          resource: s.name,
          title: "Preview URLs enabled" + (guarded ? " (behind Access)" : ""),
          detail: `Every uploaded version gets its own public <version>-${url} address, with no zone rules in front.` + (guarded ? ACCESS : ""),
          fix: PV_FIX,
          source: lw && lw.previewUrls === void 0 ? "api+local" : "api"
        });
      }
    }
  }
  for (const w of ctx.snap.local) {
    const wd = effectiveWorkersDev(w);
    if (!reported.has(w.name)) {
      if (wd.value) {
        const cron = cronOnly(w);
        out.push({
          check: "workers-dev-enabled",
          severity: cron ? "low" : "medium",
          account: "local",
          resource: w.name,
          title: wd.explicit ? "workers_dev is true in config" : "workers_dev not set and no routes, so it defaults to on",
          detail: `${w.file}${w.env ? ` [env.${w.env}]` : ""}: the next deploy publishes this Worker on workers.dev.` + (cron ? " The source shows a scheduled handler and no fetch handler, so the address would only answer with an error." : ""),
          fix: WD_FIX,
          source: "local"
        });
      } else if (!wd.explicit) {
        out.push({
          check: "workers-dev-enabled",
          severity: "info",
          account: "local",
          resource: w.name,
          title: "workers_dev not set explicitly",
          detail: `${w.file}${w.env ? ` [env.${w.env}]` : ""}: off today only because routes exist; removing the routes turns workers.dev on.`,
          fix: 'Add "workers_dev": false.',
          source: "local"
        });
      }
    }
    if (!reported.has(`preview:${w.name}`)) {
      if (w.previewUrls === true || w.previewUrls === void 0 && wd.value) {
        out.push({
          check: "preview-urls-enabled",
          severity: w.previewUrls === true ? "medium" : "low",
          account: "local",
          resource: w.name,
          title: w.previewUrls === true ? "preview_urls is true in config" : "preview_urls not set; it follows workers_dev, which is on",
          detail: `${w.file}${w.env ? ` [env.${w.env}]` : ""}`,
          fix: PV_FIX,
          source: "local"
        });
      } else if (w.previewUrls === void 0) {
        out.push({
          check: "preview-urls-enabled",
          severity: "info",
          account: "local",
          resource: w.name,
          title: "preview_urls not set explicitly",
          detail: `${w.file}${w.env ? ` [env.${w.env}]` : ""}: wrangler leaves an existing setting unchanged when the key is absent.`,
          fix: 'Add "preview_urls": false.',
          source: "local"
        });
      }
    }
  }
  return out;
}
function isPublicByPolicy(ctx, host) {
  return ctx.opts.publicHostnames.some((rule) => hostMatches(rule, host));
}
function checkHostnameAuth(ctx) {
  const out = [];
  for (const a of ctx.accounts) {
    const apps = a.snap.accessApps;
    for (const [script, hosts] of a.hostsByScript) {
      if (!a.scriptNames.has(script)) continue;
      const lw = a.local.get(script);
      const appAuth = ctx.opts.appAuthScripts.includes(script) || (lw?.authMarkers.length ?? 0) > 0;
      for (const host of hosts) {
        if (isPublicByPolicy(ctx, host) || appAuth) continue;
        const coverage = apps?.map((app) => app.domains.map((d) => accessCoverage(d, host))).flat() ?? [];
        if (coverage.includes("full")) continue;
        const partial = coverage.includes("partial");
        out.push({
          check: "hostname-without-auth",
          severity: apps === void 0 ? "low" : partial ? "low" : "medium",
          account: label(a.snap),
          resource: host,
          title: partial ? "Access covers only some paths" : "No Access application and no app sign-in found",
          detail: `Served by ${script}. ` + (apps === void 0 ? "Access applications could not be read, so this is unverified. " : partial ? "An Access app matches this host on a sub-path only. " : "No Access application matches this hostname. ") + (lw ? "The repo shows no sign-in marker." : "No local repo was scanned for this Worker, so app-level sign-in is unknown."),
          fix: `If it is meant to be public, add "${host}" to publicHostnames. Otherwise put a self-hosted Access application on it, or list the script in appAuthScripts if it signs users in itself.`,
          source: lw ? "api+local" : "api"
        });
      }
    }
  }
  for (const w of ctx.unmatchedLocal) {
    if (w.authMarkers.length > 0 || ctx.opts.appAuthScripts.includes(w.name)) continue;
    for (const r of w.routes) {
      const host = r.pattern.split("/")[0].toLowerCase();
      if (isPublicByPolicy(ctx, host)) continue;
      out.push({
        check: "hostname-without-auth",
        severity: "info",
        account: "local",
        resource: host,
        title: "No sign-in marker in the repo (Access not checked)",
        detail: `${w.file}: route for ${w.name}; no API data matched this Worker, so Access was not checked.`,
        fix: `Add "${host}" to publicHostnames if public; otherwise check it has an Access application.`,
        source: "local"
      });
    }
  }
  return out;
}

// src/core/checks/lifecycle.ts
var NON_HTTP_ENTRY = ["queue", "email", "tail", "alarm"];
function checkDeadScripts(ctx) {
  const out = [];
  for (const a of ctx.accounts) {
    const scripts = a.snap.scripts ?? [];
    const complete = a.snap.zones !== void 0 && a.snap.customDomains !== void 0 && (a.snap.zones ?? []).every((z) => z.routes !== void 0);
    const bound = new Set(scripts.flatMap((s) => (s.bindings ?? []).filter((b) => b.type === "service" && b.service).map((b) => b.service)));
    for (const s of scripts) {
      const reasons = [];
      const hosts = a.hostsByScript.get(s.name)?.size ?? 0;
      const hasCron = (s.crons?.length ?? 0) > 0 || s.crons === void 0 && s.handlers.includes("scheduled");
      const otherEntry = s.handlers.some((h) => NON_HTTP_ENTRY.includes(h));
      const reachable = hosts > 0 || s.subdomain?.enabled === true || hasCron || otherEntry || bound.has(s.name);
      if (complete && s.subdomain !== void 0 && !reachable) {
        reasons.push("no route, no custom domain, workers.dev off, no cron or queue/email handler, and no service binding points at it");
      }
      const last = s.lastDeployedOn ?? s.modifiedOn;
      const age = last ? daysBetween(new Date(last), ctx.opts.now) : void 0;
      if (age !== void 0 && age > ctx.opts.staleDays) reasons.push(`last deployed ${age} days ago (${last.slice(0, 10)})`);
      if (reasons.length === 0) continue;
      const unreachable = reasons.length === 2 || reasons[0].startsWith("no route");
      out.push({
        check: "dead-script",
        severity: reasons.length === 2 ? "medium" : "low",
        account: label(a.snap),
        resource: s.name,
        title: reasons.length === 2 ? "Unreachable and not deployed for a long time" : unreachable ? "Unreachable script" : `Not deployed for ${age} days`,
        detail: `${reasons.join("; ")}. Old scripts keep their secrets and bindings live.`,
        fix: unreachable ? `If nothing uses it: wrangler delete --name ${s.name}. Otherwise note why it is kept.` : "Redeploy to pick up runtime fixes, or delete it if retired.",
        source: "api"
      });
    }
  }
  return out;
}
function checkCompatDates(ctx) {
  const out = [];
  const limit = ctx.opts.compatMonths;
  const seen = /* @__PURE__ */ new Set();
  const make = (account, resource, date, where, source) => {
    const d = /* @__PURE__ */ new Date(`${date}T00:00:00Z`);
    if (Number.isNaN(d.getTime())) return void 0;
    const months = monthsBetween(d, ctx.opts.now);
    if (months < limit) return void 0;
    return {
      check: "compat-date-old",
      severity: months >= limit * 2 ? "medium" : "low",
      account,
      resource,
      title: `compatibility_date is ${months} months old`,
      detail: `${date}${where}. Runtime behaviour fixes after that date are off for this Worker.`,
      fix: "Read the compatibility flags changelog for the dates in between, raise compatibility_date, run the tests, redeploy.",
      source
    };
  };
  for (const a of ctx.accounts) {
    for (const s of a.snap.scripts ?? []) {
      if (!s.compatibilityDate) continue;
      const lw = a.local.get(s.name);
      const f = make(label(a.snap), s.name, s.compatibilityDate, lw ? ` (deployed; ${lw.file} has ${lw.compatibilityDate ?? "none"})` : " (deployed)", lw ? "api+local" : "api");
      if (f) out.push(f);
      seen.add(s.name);
    }
  }
  for (const w of ctx.snap.local) {
    if (seen.has(w.name) || !w.compatibilityDate) continue;
    const f = make("local", w.name, w.compatibilityDate, ` in ${w.file}`, "local");
    if (f) out.push(f);
  }
  return out;
}
function checkSecrets(ctx) {
  const findings = [];
  const baseline = {};
  const prev = ctx.opts.secretsBaseline;
  for (const a of ctx.accounts) {
    for (const s of a.snap.scripts ?? []) {
      if (!s.secretNames) continue;
      const key = `${a.snap.id}/${s.name}`;
      baseline[key] = [...s.secretNames];
      const before = prev?.[key];
      if (!before) continue;
      const added = s.secretNames.filter((n) => !before.includes(n));
      const removed = before.filter((n) => !s.secretNames.includes(n));
      if (added.length === 0 && removed.length === 0) continue;
      findings.push({
        check: "secrets-changed",
        severity: removed.length ? "medium" : "low",
        account: label(a.snap),
        resource: s.name,
        title: `Secrets changed: ${s.secretNames.length} now, ${before.length} before`,
        detail: [added.length ? `added ${added.join(", ")}` : "", removed.length ? `removed ${removed.join(", ")}` : ""].filter(Boolean).join("; ") + ". Names only; values are never read.",
        fix: "Confirm the change was yours (wrangler secret list). A removed secret often breaks the next request that needs it.",
        source: "api"
      });
    }
  }
  for (const [k, v] of Object.entries(prev ?? {})) if (!(k in baseline)) baseline[k] = v;
  return { findings, baseline };
}

// src/core/checks/ratelimit.ts
function nextFreeBlock(ids) {
  const nums = ids.map(Number).filter((n) => Number.isInteger(n) && n >= 0);
  if (nums.length === 0) return void 0;
  return String((Math.floor(Math.max(...nums) / 100) + 1) * 100 + 1);
}
function findingsFor(pool, account) {
  const out = [];
  const free = nextFreeBlock([...pool.keys()]);
  for (const [id, uses] of [...pool].sort(([a], [b]) => a.localeCompare(b, "en", { numeric: true }))) {
    const unique = /* @__PURE__ */ new Map();
    for (const u of uses) {
      const k = `${u.worker}\0${u.binding}`;
      const prev = unique.get(k);
      unique.set(k, prev && prev.from !== u.from ? { ...prev, from: "api", file: prev.file ?? u.file } : prev ?? u);
    }
    const list = [...unique.values()];
    const workers = [...new Set(list.map((u) => u.worker))].sort();
    const sources = new Set(uses.map((u) => u.from));
    const source = sources.size === 2 ? "api+local" : sources.has("api") ? "api" : "local";
    const where = list.map((u) => `${u.worker}.${u.binding}${u.file ? ` (${u.file})` : ""}`).join(", ");
    if (workers.length > 1) {
      out.push({
        check: "ratelimit-namespace-shared",
        severity: "high",
        account,
        resource: `namespace ${id}`,
        title: `Rate-limit namespace ${id} shared by ${workers.length} Workers`,
        detail: `${where}. They share counters, so traffic to one spends the others' limit.`,
        fix: `Give each Worker its own ids${free ? ` (next free block: ${free}-${Number(free) + 98})` : ""} and redeploy each.`,
        source
      });
    } else if (list.length > 1) {
      out.push({
        check: "ratelimit-namespace-shared",
        severity: "medium",
        account,
        resource: `namespace ${id}`,
        title: `Two limits in ${workers[0]} share namespace ${id}`,
        detail: `${where}. Both bindings count against the same counters, so neither limit holds as written.`,
        fix: `Give each binding its own namespace_id${free ? ` (next free block: ${free})` : ""}.`,
        source
      });
    }
  }
  return out;
}
function checkRatelimitNamespaces(ctx) {
  const out = [];
  const add = (pool, id, u) => {
    if (!pool.has(id)) pool.set(id, []);
    pool.get(id).push(u);
  };
  const single = ctx.accounts.length === 1;
  for (const a of ctx.accounts) {
    const pool = /* @__PURE__ */ new Map();
    for (const s of a.snap.scripts ?? []) {
      for (const b of s.bindings ?? []) if (b.type === "ratelimit" && b.namespaceId) add(pool, b.namespaceId, { worker: s.name, binding: b.name, from: "api" });
    }
    const locals = [...a.local.values(), ...single ? ctx.unmatchedLocal : []];
    for (const w of locals) for (const r of w.ratelimitNamespaces) add(pool, r.namespaceId, { worker: w.name, binding: r.binding, from: "local", file: w.file });
    out.push(...findingsFor(pool, label(a.snap)));
  }
  if (!single) {
    const pool = /* @__PURE__ */ new Map();
    for (const w of ctx.unmatchedLocal) for (const r of w.ratelimitNamespaces) add(pool, r.namespaceId, { worker: w.name, binding: r.binding, from: "local", file: w.file });
    out.push(...findingsFor(pool, "local"));
  }
  return out;
}

// src/core/checks/routing.ts
function checkRoutesToMissingScripts(ctx) {
  const out = [];
  for (const a of ctx.accounts) {
    if (!a.snap.scripts) continue;
    for (const z of a.snap.zones ?? []) {
      for (const r of z.routes ?? []) {
        if (r.script && !a.scriptNames.has(r.script)) {
          out.push({
            check: "route-to-missing-script",
            severity: "high",
            account: label(a.snap),
            resource: r.pattern,
            title: `Route points at deleted Worker "${r.script}"`,
            detail: `Zone ${z.name}, route id ${r.id}. Requests here get an error, and a new script with that name would take the route over.`,
            fix: `Delete the route (zone ${z.name} > Workers Routes), or redeploy "${r.script}" if it should exist.`,
            source: "api"
          });
        }
      }
    }
    for (const d of a.snap.customDomains ?? []) {
      if (!a.scriptNames.has(d.service)) {
        out.push({
          check: "route-to-missing-script",
          severity: "high",
          account: label(a.snap),
          resource: d.hostname,
          title: `Custom domain bound to missing Worker "${d.service}"`,
          detail: `Zone ${d.zoneName ?? d.zoneId ?? "?"}.`,
          fix: `Detach the custom domain, or redeploy "${d.service}".`,
          source: "api"
        });
      }
    }
  }
  return out;
}
var PLACEHOLDER_A = /^192\.0\.2\.\d+$/;
var PLACEHOLDER_AAAA = /^100::(0)?$/i;
function checkDanglingDns(ctx) {
  const out = [];
  for (const a of ctx.accounts) {
    const zones = a.snap.zones ?? [];
    const routeHosts = zones.flatMap((z) => (z.routes ?? []).filter((r) => r.script).map((r) => hostOf(r.pattern)));
    const customHosts = new Set((a.snap.customDomains ?? []).map((d) => d.hostname.toLowerCase()));
    const namesByZone = new Map(zones.filter((z) => z.dns).map((z) => [z.name.toLowerCase(), new Set(z.dns.map((r) => r.name.toLowerCase()))]));
    const scripts = new Map((a.snap.scripts ?? []).map((s) => [s.name, s]));
    for (const z of zones) {
      for (const rec of z.dns ?? []) {
        const name = rec.name.toLowerCase();
        const target = rec.content.toLowerCase().replace(/\.$/, "");
        if (rec.type === "CNAME" && target.endsWith(".workers.dev") && a.snap.scripts) {
          const [script, sub] = target.split(".");
          const s = script ? scripts.get(script) : void 0;
          const otherSub = a.snap.workersSubdomain && sub !== a.snap.workersSubdomain.toLowerCase();
          if (otherSub || !s || s.subdomain?.enabled === false) {
            out.push({
              check: "dangling-dns",
              severity: otherSub ? "medium" : "high",
              account: label(a.snap),
              resource: name,
              title: otherSub ? "CNAME into a different workers.dev subdomain" : !s ? `CNAME to workers.dev for missing Worker "${script}"` : `CNAME to "${script}" on workers.dev, which is disabled`,
              detail: `${z.name}: ${name} CNAME ${target}.${otherSub ? ` This account's subdomain is ${a.snap.workersSubdomain}; the target belongs to another account or a renamed subdomain.` : ""}`,
              fix: "Delete the record, or replace it with a Workers custom domain on the script it should serve.",
              source: "api"
            });
          }
          continue;
        }
        if (rec.type === "CNAME") {
          const zoneOfTarget = [...namesByZone.keys()].find((zn) => target === zn || target.endsWith(`.${zn}`));
          if (zoneOfTarget && !namesByZone.get(zoneOfTarget).has(target) && !customHosts.has(target)) {
            const wildcard = [...namesByZone.get(zoneOfTarget)].some((n) => n.startsWith("*.") && hostMatches(n, target));
            if (!wildcard) {
              out.push({
                check: "dangling-dns",
                severity: "medium",
                account: label(a.snap),
                resource: name,
                title: "CNAME to a name that no longer exists",
                detail: `${z.name}: ${name} CNAME ${target}, and zone ${zoneOfTarget} has no record for ${target}.`,
                fix: "Delete the record, or recreate its target.",
                source: "api"
              });
            }
          }
          continue;
        }
        const placeholder = rec.type === "A" && PLACEHOLDER_A.test(target) || rec.type === "AAAA" && PLACEHOLDER_AAAA.test(target);
        if (placeholder && a.snap.zones?.every((zz) => zz.routes !== void 0)) {
          const served = routeHosts.some((h) => hostMatches(h, name)) || customHosts.has(name);
          if (!served) {
            out.push({
              check: "dangling-dns",
              severity: "medium",
              account: label(a.snap),
              resource: name,
              title: "Placeholder record with no Workers route",
              detail: `${z.name}: ${name} ${rec.type} ${rec.content}${rec.proxied ? " (proxied)" : ""}. That address only exists to carry a Workers route, and no route matches it any more.`,
              fix: "Delete the record, or add the route back.",
              source: "api"
            });
          }
        }
      }
    }
  }
  return out;
}

// src/core/checks/tokens.ts
var WRITE = /\b(write|edit|admin)\b/i;
var ALL_RESOURCES = /^com\.cloudflare\.api\.(account|user)\.\*$|^com\.cloudflare\.api\.account\.zone\.\*$/;
var BROAD_WRITE_GROUPS = 8;
var UNUSED_DAYS = 90;
function tokenIssues(t, now) {
  const out = [];
  if (t.status && t.status !== "active") return out;
  const resource = `${t.name} (${t.scope} token)`;
  const writes = t.policies.filter((p) => p.effect === "allow").flatMap((p) => p.permissionGroups.filter((g) => WRITE.test(g)).map((g) => ({ g, p })));
  const everywhere = writes.filter(({ p }) => p.resources.some((r) => ALL_RESOURCES.test(r)));
  const uniqueWrites = [...new Set(writes.map((w) => w.g))];
  if (everywhere.length > 0) {
    const groups = [...new Set(everywhere.map((w) => w.g))];
    out.push({
      check: "token-over-scoped",
      severity: "high",
      resource,
      title: "Write access on all accounts or all zones",
      detail: `${groups.slice(0, 6).join(", ")}${groups.length > 6 ? ` and ${groups.length - 6} more` : ""} on every ${everywhere.some(({ p }) => p.resources.some((r) => r.includes("zone"))) ? "zone" : "account"}.${t.ipRestricted ? "" : " No client IP restriction."}`,
      fix: "Roll a replacement scoped to the one account and the zones it needs, then delete this one."
    });
  } else if (uniqueWrites.length >= BROAD_WRITE_GROUPS) {
    out.push({
      check: "token-over-scoped",
      severity: "medium",
      resource,
      title: `${uniqueWrites.length} write permission groups`,
      detail: `${uniqueWrites.slice(0, 6).join(", ")}, ... A token this broad is usually several jobs sharing one secret.`,
      fix: "Split it into one token per job, each with only what that job writes."
    });
  }
  if (!t.expiresOn) {
    out.push({
      check: "token-no-expiry",
      severity: writes.length ? "medium" : "low",
      resource,
      title: "Never expires",
      detail: `Issued ${t.issuedOn?.slice(0, 10) ?? "on an unknown date"}${writes.length ? ", with write access" : ""}.`,
      fix: "Set an expiry (Edit token > TTL) and a reminder to roll it."
    });
  }
  const lastUsed = t.lastUsedOn ? daysBetween(new Date(t.lastUsedOn), now) : void 0;
  if (lastUsed !== void 0 && lastUsed > UNUSED_DAYS) {
    out.push({
      check: "token-unused",
      severity: "low",
      resource,
      title: `Unused for ${lastUsed} days`,
      detail: `Last used ${t.lastUsedOn.slice(0, 10)}.`,
      fix: "Delete it if nothing needs it."
    });
  }
  return out;
}
function checkTokens(ctx) {
  const seen = /* @__PURE__ */ new Set();
  const out = [];
  for (const a of ctx.accounts) {
    for (const t of a.snap.tokens ?? []) {
      if (seen.has(t.id)) continue;
      seen.add(t.id);
      for (const f of tokenIssues(t, ctx.opts.now)) out.push({ ...f, account: t.scope === "user" ? "user" : label(a.snap), source: "api" });
    }
  }
  return out;
}

// src/core/checks/zones.ts
var HSTS_MIN_AGE = 15552e3;
function checkZoneTls(ctx) {
  const out = [];
  for (const a of ctx.accounts) {
    for (const z of a.snap.zones ?? []) {
      if (z.status && z.status !== "active") continue;
      const s = z.settings;
      if (!s) continue;
      const push = (severity, title, detail, fix) => out.push({ check: "zone-tls", severity, account: label(a.snap), resource: z.name, title, detail, fix, source: "api" });
      if (s.minTlsVersion && Number(s.minTlsVersion) < 1.2) {
        push("medium", `Minimum TLS ${s.minTlsVersion}`, "TLS 1.0 and 1.1 are deprecated and fail PCI DSS.", "SSL/TLS > Edge Certificates > Minimum TLS Version: 1.2.");
      }
      if (s.alwaysUseHttps === "off") {
        push("medium", "Always Use HTTPS is off", "Plain-HTTP requests are served instead of redirected.", "SSL/TLS > Edge Certificates > Always Use HTTPS: on.");
      }
      if (s.hsts && !s.hsts.enabled) {
        push("low", "HSTS off", "Browsers will try plain HTTP first on every new visit.", "SSL/TLS > Edge Certificates > HTTP Strict Transport Security: enable, max-age 6 months or more, once every subdomain serves HTTPS.");
      } else if (s.hsts && s.hsts.maxAge < HSTS_MIN_AGE) {
        push("low", `HSTS max-age ${s.hsts.maxAge}s`, "Below 6 months, so it lapses for visitors who come back rarely.", "Raise max-age to 15552000 or more.");
      }
    }
  }
  return out;
}

// src/core/types.ts
var SEVERITIES = ["critical", "high", "medium", "low", "info"];
var severityRank = (s) => SEVERITIES.length - SEVERITIES.indexOf(s);
var CHECK_IDS = [
  "workers-dev-enabled",
  "preview-urls-enabled",
  "hostname-without-auth",
  "ratelimit-namespace-shared",
  "route-to-missing-script",
  "dangling-dns",
  "dead-script",
  "compat-date-old",
  "secrets-changed",
  "token-over-scoped",
  "token-no-expiry",
  "token-unused",
  "zone-tls"
];
var DEFAULT_OPTIONS = {
  publicHostnames: [],
  appAuthScripts: [],
  staleDays: 180,
  compatMonths: 12
};

// src/core/audit.ts
function audit(snap, opts) {
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
    ...checkZoneTls(ctx)
  ].sort((a, b) => severityRank(b.severity) - severityRank(a.severity) || a.check.localeCompare(b.check) || a.account.localeCompare(b.account) || a.resource.localeCompare(b.resource));
  const summary = Object.fromEntries(SEVERITIES.map((s) => [s, 0]));
  for (const f of findings) summary[f.severity]++;
  return {
    result: {
      generatedAt: opts.now.toISOString(),
      findings,
      gaps: [...snap.accounts.flatMap((a) => a.gaps), ...snap.localGaps],
      summary,
      accounts: snap.accounts.map((a) => ({ id: a.id, name: a.name, scripts: a.scripts?.length ?? 0, zones: a.zones?.length ?? 0 })),
      localFiles: new Set(snap.local.map((w) => w.file)).size
    },
    secretsBaseline: secrets.baseline
  };
}
async function collectSnapshot(input) {
  const accounts = [];
  const calls = [];
  const localGaps = [];
  for (const [i, token] of input.tokens.entries()) {
    const client = new CfClient({ token, fetch: input.fetch, ...input.concurrency ? { concurrency: input.concurrency } : {} });
    try {
      for (const a of await collectToken(client, input.collect)) if (!accounts.some((x) => x.id === a.id)) accounts.push(a);
    } catch (e) {
      localGaps.push({ account: `token #${i + 1}`, what: "account list", reason: describeError(e) });
    }
    calls.push(...client.calls);
  }
  return { snapshot: { takenAt: input.now.toISOString(), accounts, local: input.local ?? [], localGaps }, calls };
}
function failsAt(result, threshold) {
  if (threshold === "never") return false;
  return result.findings.some((f) => severityRank(f.severity) >= severityRank(threshold));
}

// src/core/ingest.ts
var INGEST_SCHEMA = "dawnfix.flare/1";
var MAX_INGEST_ACCOUNTS = 100;
var ACCOUNT_SALT = "dawnfix.flare/1:account:";
var zero = () => Object.fromEntries(SEVERITIES.map((s) => [s, 0]));
async function hashAccountId(id) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(ACCOUNT_SALT + id));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}
async function ingestDoc(result) {
  if (result.accounts.length > MAX_INGEST_ACCOUNTS) {
    throw new Error(`${result.accounts.length} accounts in one run; the ingest takes at most ${MAX_INGEST_ACCOUNTS}`);
  }
  const findings = Object.fromEntries(CHECK_IDS.map((c) => [c, zero()]));
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
    findings
  };
}

// src/core/report/doc-style.ts
var DOC_STYLE = `
/* the document style (green Tech-Azur), one sheet for docs pages and reports */
:root{--doc-bg:#0e1013;--doc-card:#121418;--doc-text:#e6e8eb;--doc-soft:#b9bec6;--doc-accent:#7ad69a;--doc-rule:#2a2e35;--doc-border:#353a42;
--doc-th:#13261a;--doc-code:#1b1e23;--doc-pre:#14161a;--doc-tint:#10201a;
--doc-good-bg:#0f2a28;--doc-good:#5fd0c3;--doc-good-line:#1f5650;--doc-crit:#f28b82;--doc-weak:#f3b267}
@media (prefers-color-scheme:light),print{:root{--doc-bg:#ffffff;--doc-card:#ffffff;--doc-text:#1d1d1f;--doc-soft:#4a4f57;--doc-accent:#1a5e33;--doc-rule:#e1e4e8;--doc-border:#d5dae1;
--doc-th:#eaf4ec;--doc-code:#f1f3f6;--doc-pre:#f6f8fa;--doc-tint:#eaf4ec;
--doc-good-bg:#dff3f1;--doc-good:#0a5f57;--doc-good-line:#93d1c9;--doc-crit:#b3261e;--doc-weak:#a35200}}
body.doc-page{margin:0;background:var(--doc-bg);color:var(--doc-text);-webkit-text-size-adjust:100%;overflow-wrap:break-word}
body.doc-page *{box-sizing:border-box}
body.doc-page>main{max-width:960px;margin:0 auto;padding:32px 16px 56px}
article.doc{counter-reset:doc-h2;font-family:"DejaVu Sans",Verdana,"Segoe UI",system-ui,sans-serif;font-size:15px;line-height:1.55;color:var(--doc-text);-webkit-font-smoothing:auto;min-width:0}
article.doc h1{font-family:inherit;font-size:clamp(24px,3.4vw,30px);font-weight:700;letter-spacing:0;line-height:1.25;margin:0 0 14px;padding:0 0 8px;border-bottom:3px solid var(--doc-accent);color:var(--doc-text);background:none;max-width:none}
article.doc .page-head{align-items:flex-end}
article.doc .page-head h1{flex:1;margin-bottom:0}
article.doc .page-head+p,article.doc .page-head+.works{margin-top:14px}
article.doc .lead{font-size:16px;color:var(--doc-text);margin:0 0 24px;max-width:76ch}
article.doc .muted,article.doc .meta{color:var(--doc-soft)}
article.doc .eyebrow{font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--doc-accent);margin:0 0 6px}
article.doc h2{counter-increment:doc-h2;font-family:inherit;font-size:20px;font-weight:700;letter-spacing:0;line-height:1.3;color:var(--doc-accent);margin:36px 0 12px;padding-top:0;border-top:0;display:flex;gap:6px 10px;align-items:center;flex-wrap:wrap}
article.doc h2::before{content:counter(doc-h2) ".";font-variant-numeric:tabular-nums}
article.doc h2 svg.px{width:24px;height:24px}
article.doc h3,article.doc h4{font-family:inherit;font-size:15.5px;font-weight:700;letter-spacing:0;margin:22px 0 8px;color:var(--doc-text)}
article.doc p,article.doc li{color:var(--doc-text)}
article.doc p{margin:0 0 10px;max-width:80ch}
article.doc p.works{margin:12px 0 18px;font-size:14px}
article.doc a{color:var(--doc-accent);text-decoration:underline;text-decoration-color:color-mix(in srgb,var(--doc-accent) 40%,transparent);text-underline-offset:3px}
article.doc a:hover{text-decoration-color:currentColor}
article.doc hr{border:0;border-top:1px solid var(--doc-rule);margin:20px 0}
article.doc blockquote{margin:0 0 10px;padding:2px 12px;border-left:3px solid var(--doc-border);color:var(--doc-soft)}
article.doc mark{background:#fff1a8;color:#1d1d1f;padding:0 2px}

/* bullets: a small diamond, a hollow circle when nested */
article.doc ul:not(.checks):not(.plain){list-style:none;padding-left:22px;margin:0 0 10px}
article.doc ul:not(.checks):not(.plain)>li,article.doc ul.checks>li{position:relative}
article.doc ul.checks{gap:6px;margin:0 0 12px}
article.doc ul.checks li{padding-left:22px}
article.doc ul:not(.checks):not(.plain)>li::before,article.doc ul.checks>li::before{content:"\\25C6";position:absolute;left:4px;top:.42em;width:auto;height:auto;background:none;box-shadow:none;font-size:9px;line-height:1;color:var(--doc-text)}
article.doc ul:not(.checks):not(.plain)>li::before{left:-17px}
article.doc ul ul>li::before,article.doc ul.checks ul>li::before{content:"\\25E6";font-size:13px;top:.22em}
article.doc ul.plain{list-style:none;padding:0;margin:0 0 10px}
article.doc ol:not(.steps):not(.plain){padding-left:22px;margin:0 0 10px}
article.doc li{margin:2px 0}

/* numbered steps: a green numeral in a square, a thin rule between */
article.doc ol.steps>li{padding:0 0 22px 44px}
article.doc ol.steps>li::before{width:28px;height:28px;top:-1px;border-radius:3px;background:var(--doc-th);border:1px solid color-mix(in srgb,var(--doc-accent) 45%,transparent);color:var(--doc-accent);font:700 13px/1 "DejaVu Sans Mono",Menlo,Consolas,ui-monospace,monospace}
article.doc ol.steps>li::after{left:14px;top:32px;background:var(--doc-border)}
article.doc ol.steps>li>strong:first-child{font-weight:700;margin-bottom:6px}

/* code: grey, thin border, scrolls inside its box */
article.doc code,article.doc .mono{font-family:"DejaVu Sans Mono",Menlo,Consolas,ui-monospace,monospace;font-size:.85em;color:var(--doc-text)}
article.doc code{background:var(--doc-code);border:0;border-radius:3px;padding:1px 4px;overflow-wrap:anywhere}
article.doc figure.code,article.doc figure.snip{margin:0 0 14px;border:1px solid var(--doc-border);border-radius:3px;background:var(--doc-pre)}
article.doc figure.code figcaption,article.doc figure.snip figcaption{background:var(--doc-th);border-bottom:1px solid var(--doc-border);color:var(--doc-text);font-size:13px;font-weight:700;padding:6px 12px}
article.doc pre{font-family:"DejaVu Sans Mono",Menlo,Consolas,ui-monospace,monospace;background:var(--doc-pre);border:1px solid var(--doc-border);border-radius:3px;padding:12px 14px;margin:0 0 14px;font-size:13px;line-height:1.45;color:var(--doc-text);overflow-x:auto;max-width:100%}
article.doc pre.wrap-lines{white-space:pre-wrap;overflow-wrap:anywhere}
article.doc figure pre{border:0;border-radius:0;margin:0}
article.doc pre code{background:none;padding:0;font-size:inherit;border-radius:0;overflow-wrap:normal}
article.doc details:not(.docs-nav){margin:0 0 14px;border:1px solid var(--doc-border);border-radius:3px;padding:8px 12px;background:var(--doc-card)}
article.doc details:not(.docs-nav)>summary{cursor:pointer;font-weight:700}
article.doc details:not(.docs-nav)[open]>summary{margin-bottom:8px}
article.doc details pre{margin-bottom:4px}

/* tables: in a wrapper that scrolls on a phone, never the page */
article.doc .table-wrap,article.doc .wrap{overflow-x:auto;margin:6px 0 14px;max-width:100%}
article.doc table{width:100%;border-collapse:collapse;font-size:13.5px;margin:0}
article.doc th,article.doc td{border:1px solid var(--doc-border);padding:6px 8px;text-align:left;vertical-align:top;color:var(--doc-text);background:none}
article.doc th{background:var(--doc-th);font-weight:700;font-size:13px}
article.doc th.n,article.doc td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}

/* key figures: thin-bordered boxes in a row, two to a line on a phone */
article.doc .facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:0;margin:6px 0 18px;border:1px solid var(--doc-border);border-radius:3px;overflow:hidden}
article.doc .facts>div{padding:10px 12px;border-right:1px solid var(--doc-border);border-bottom:1px solid var(--doc-border);margin:-1px -1px 0 0;background:var(--doc-card)}
article.doc .facts>div:first-child,article.doc .facts>div.lead-fact{background:var(--doc-tint)}
article.doc .facts b{display:block;font-size:21px;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.25}
article.doc .facts span{display:block;font-size:12.5px;color:var(--doc-soft)}
article.doc .facts .good b{color:var(--doc-good)}
article.doc .facts .crit b,article.doc .crit-text{color:var(--doc-crit)}
article.doc .facts .weak b,article.doc .weak-text{color:var(--doc-weak)}

/* the site's cards (stat tiles) inside a document: square, thin, the doc's border */
article.doc .card{border-radius:3px;border:1px solid var(--doc-border);background:var(--doc-card);box-shadow:none}
article.doc .card b{font-weight:700}

/* items: one bordered block each (a finding, a saving), the label column tinted */
article.doc .items{list-style:none;padding:0;margin:0 0 12px;display:grid;gap:8px}
article.doc .items>li{margin:0;padding:10px 14px;border:1px solid var(--doc-border);border-left:4px solid var(--doc-accent);border-radius:3px;background:var(--doc-card);min-width:0}
article.doc .items>li::before{content:none}
article.doc .items>li.crit{border-left-color:#c62828}
article.doc .items>li.weak{border-left-color:#e07a00}
article.doc .items>li.mixed{border-left-color:#c9a400}
article.doc .items>li.unknown{border-left-color:#8a8f98}
article.doc .items .head{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline}
article.doc .items .head b{font-weight:700}
article.doc .items .head .end{margin-left:auto}
article.doc .items pre{margin:8px 0 2px;white-space:pre-wrap;overflow-wrap:anywhere}
article.doc .items p{margin:4px 0 0}

/* highlights: status pills, priority tags, callouts */
article.doc .pill,article.doc .pri{display:inline-block;font-family:inherit;font-weight:700;font-size:11.5px;line-height:1.35;padding:1px 7px;border-radius:9px;white-space:nowrap;letter-spacing:0;border:1px solid var(--doc-border);background:var(--doc-code);color:var(--doc-soft);text-transform:none}
article.doc .pill.crit{background:#fde2e1;color:#b3261e;border-color:#f1a7a3}
article.doc .pill.weak{background:#fff0db;color:#a35200;border-color:#f3c48a}
article.doc .pill.mixed{background:#fff8cc;color:#7a6300;border-color:#e8d777}
article.doc .pill.good{background:var(--doc-good-bg);color:var(--doc-good);border-color:var(--doc-good-line)}
article.doc .pill.unknown{background:#eceef1;color:#555b65;border-color:#c7ccd3}
article.doc .pill.accent{background:var(--doc-tint);color:var(--doc-accent);border-color:color-mix(in srgb,var(--doc-accent) 45%,transparent)}
article.doc .pri{border-radius:3px;border:0;color:#fff;padding:1px 5px}
article.doc .pri.p0{background:#c62828}
article.doc .pri.p1{background:#b86400}
article.doc .pri.p2{background:#6b7079}
article.doc .callout{display:block;margin:6px 0 14px;padding:10px 14px 2px;border:0;border-left:4px solid var(--doc-border);border-radius:3px;background:var(--doc-code);color:var(--doc-text)}
article.doc .callout.red{background:color-mix(in srgb,#c62828 10%,transparent);border-left-color:#c62828}
article.doc .callout.amber{background:color-mix(in srgb,#e07a00 10%,transparent);border-left-color:#e07a00}
article.doc .callout.accent{background:var(--doc-tint);border-left-color:var(--doc-accent)}
article.doc .callout.green{background:var(--doc-good-bg);border-left-color:var(--doc-good)}
article.doc .callout p{margin-bottom:8px}
article.doc p.callout{max-width:none;padding-bottom:10px}
article.doc footer{margin-top:36px;padding-top:12px;border-top:1px solid var(--doc-rule);font-size:13px;color:var(--doc-soft)}
article.doc footer p{margin:0 0 6px}

/* the site's buttons and pager inside a document: squarer, in the document's face */
article.doc .actions{margin:14px 0 0}
article.doc .btn,article.doc .button{font-family:inherit;border-radius:3px}
article.doc .pager a{border-radius:3px}
@media (max-width:600px){article.doc{font-size:15px}article.doc h2{font-size:18.5px;margin-top:30px}article.doc pre{font-size:12.5px}article.doc .facts{grid-template-columns:1fr 1fr}body.doc-page>main{padding:20px 16px 40px}}
@media print{body.doc-page>main{max-width:none;padding:0}article.doc .wrap,article.doc .table-wrap,article.doc pre{overflow:visible;white-space:pre-wrap}}
`;

// src/core/report/html.ts
var esc = (s) => String(s).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
var CHECK_NAMES = {
  "workers-dev-enabled": "workers.dev exposure",
  "preview-urls-enabled": "Preview URLs",
  "hostname-without-auth": "Hostname without auth",
  "ratelimit-namespace-shared": "Rate-limit namespace clash",
  "route-to-missing-script": "Route to missing Worker",
  "dangling-dns": "Dangling DNS",
  "dead-script": "Dead script",
  "compat-date-old": "Old compatibility date",
  "secrets-changed": "Secrets changed",
  "token-over-scoped": "Over-scoped token",
  "token-no-expiry": "Token never expires",
  "token-unused": "Unused token",
  "zone-tls": "Zone TLS / HSTS"
};
var SEVERITY_PILL = {
  critical: "pri p0",
  high: "pill crit",
  medium: "pill weak",
  low: "pill mixed",
  info: "pill unknown"
};
var REPORT_CSS = `
article.doc .chips{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 20px}
article.doc .chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--doc-border);background:var(--doc-card);color:var(--doc-text);border-radius:3px;padding:5px 10px;font:inherit;font-size:14px;cursor:pointer}
article.doc .chip[aria-pressed="false"]{opacity:.45}
article.doc .chip b{font-variant-numeric:tabular-nums}
article.doc .items>li.f[data-sev=critical],article.doc .items>li.f[data-sev=high]{border-left-color:#c62828}
article.doc .items>li.f[data-sev=medium]{border-left-color:#e07a00}
article.doc .items>li.f[data-sev=low]{border-left-color:#c9a400}
article.doc .items>li.f[data-sev=info]{border-left-color:#8a8f98}
article.doc .f .chk{font-weight:700}
article.doc .f .acct{color:var(--doc-soft);font-size:13px}
article.doc .f .res{display:block;margin-top:6px;overflow-wrap:anywhere}
article.doc .f .title{font-weight:700;margin-top:2px}
article.doc .f .detail{color:var(--doc-soft);overflow-wrap:anywhere}
article.doc .f .fix{overflow-wrap:anywhere}
article.doc .f .fix b{color:var(--doc-accent);margin-right:4px}
@media (max-width:560px){article.doc .items .head .end{margin-left:0;width:100%}}
`;
function renderHtml(r) {
  const counts = SEVERITIES.map((s) => [s, r.summary[s]]);
  const rows = r.findings.map(
    (f) => `<li class="f" data-sev="${f.severity}">
  <div class="head"><span class="${SEVERITY_PILL[f.severity]}">${esc(f.severity)}</span><span class="chk">${esc(CHECK_NAMES[f.check] ?? f.check)}</span><span class="end acct">${esc(f.account)} · ${esc(f.source)}</span></div>
  <code class="res">${esc(f.resource)}</code>
  <div class="title">${esc(f.title)}</div>
  <p class="detail">${esc(f.detail)}</p>
  <p class="fix"><b>Fix</b> ${esc(f.fix)}</p>
</li>`
  ).join("\n");
  const gaps = r.gaps.length ? `<h2>Not checked</h2><p class="muted">These parts could not be read with the token given, so their checks did not run.</p><ul class="gaps">${r.gaps.map((g) => `<li><b>${esc(g.account)}</b> ${esc(g.what)} <span class="muted">— ${esc(g.reason)}</span></li>`).join("")}</ul>` : "";
  const accounts = r.accounts.map((a) => `<tr><td>${esc(a.name)}</td><td class="n">${esc(a.scripts)}</td><td class="n">${esc(a.zones)}</td></tr>`).join("");
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>${esc(BRAND.product)} audit</title>
<style>${DOC_STYLE}${REPORT_CSS}</style>
</head>
<body class="doc-page">
<main>
<article class="doc">
<p class="eyebrow">${esc(BRAND.fullName)}</p>
<h1>Cloudflare account and Workers audit</h1>
<p class="meta">${esc(r.generatedAt.slice(0, 16).replace("T", " "))} UTC · ${esc(r.accounts.length)} account(s) · ${esc(r.localFiles)} local wrangler file(s) · read-only</p>
<h2>Findings</h2>
<div class="chips" role="group" aria-label="Filter by severity">
${counts.map(([s, n]) => `<button class="chip" type="button" aria-pressed="true" data-filter="${s}"><span class="${SEVERITY_PILL[s]}">${s}</span> <b>${n}</b></button>`).join("\n")}
</div>
${r.findings.length ? `<ul class="items plain" id="findings">${rows}</ul>` : '<p class="callout green">No findings.</p>'}
${gaps}
<h2>Accounts</h2>
<div class="wrap"><table><thead><tr><th>Account</th><th class="n">Scripts</th><th class="n">Zones</th></tr></thead><tbody>${accounts || '<tr><td colspan="3" class="muted">None (local files only)</td></tr>'}</tbody></table></div>
<footer>${esc(BRAND.fullName)} · ${esc(BRAND.org)} · Generated with read-only API calls; secret values are never read.</footer>
</article>
</main>
<script>
document.querySelectorAll('.chip').forEach(function(b){b.addEventListener('click',function(){
var on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',String(on));
document.querySelectorAll('.f[data-sev="'+b.dataset.filter+'"]').forEach(function(li){li.hidden=!on;});});});
</script>
</body>
</html>
`;
}

// src/core/report/markdown.ts
var MAX_SUMMARY_ROWS = 300;
var mdCell = (s) => String(s).replace(/[\r\n]+/g, " ").replace(/\\/g, "\\\\").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/`/g, "'").replace(/([*_[\]|])/g, "\\$1");
function renderMarkdown(r) {
  const counts = SEVERITIES.filter((s) => r.summary[s] > 0).map((s) => `${r.summary[s]} ${s}`);
  const lines = [
    `## ${BRAND.fullName}: Cloudflare audit`,
    "",
    `${r.generatedAt.slice(0, 16).replace("T", " ")} UTC · ${r.accounts.length} account(s) · ${r.localFiles} wrangler file(s) · read-only. **${counts.length ? counts.join(", ") : "no findings"}**.`,
    ""
  ];
  if (r.findings.length) {
    lines.push("| Severity | Check | Account | Resource | Finding | Fix |", "|---|---|---|---|---|---|");
    for (const f of r.findings.slice(0, MAX_SUMMARY_ROWS)) {
      lines.push(`| ${f.severity} | ${mdCell(CHECK_NAMES[f.check] ?? f.check)} | ${mdCell(f.account)} | ${mdCell(f.resource)} | ${mdCell(f.title)} | ${mdCell(f.fix)} |`);
    }
    if (r.findings.length > MAX_SUMMARY_ROWS) lines.push("", `${r.findings.length - MAX_SUMMARY_ROWS} more not shown; run the CLI with --html for all of them.`);
    lines.push("");
  }
  if (r.gaps.length) {
    lines.push(`<details><summary>Not checked (${r.gaps.length})</summary>`, "", ...r.gaps.map((g) => `- ${mdCell(g.account)}: ${mdCell(g.what)} (${mdCell(g.reason)})`), "", "</details>", "");
  }
  return lines.join("\n") + "\n";
}

// src/core/report/text.ts
var COLORS = { critical: "\x1B[1;37;41m", high: "\x1B[31m", medium: "\x1B[33m", low: "\x1B[36m", info: "\x1B[2m" };
var RESET = "\x1B[0m";
var DIM = "\x1B[2m";
function cut(s, w) {
  return s.length <= w ? s.padEnd(w) : `${s.slice(0, w - 1)}…`;
}
function renderText(r, opts = {}) {
  const color = opts.color ?? false;
  const width = Math.max(80, opts.width ?? 120);
  const c = (code, s) => color ? `${code}${s}${RESET}` : s;
  const lines = [];
  const acc = r.accounts.map((a) => `${a.name} (${a.scripts} scripts, ${a.zones} zones)`).join(", ") || "none";
  lines.push(`${BRAND.fullName} — ${r.generatedAt.slice(0, 16).replace("T", " ")} UTC`);
  lines.push(`Accounts: ${acc}. Local wrangler files: ${r.localFiles}.`);
  lines.push("");
  const findings = r.findings;
  if (findings.length === 0) lines.push("No findings.");
  else {
    const wSev = 8, wCheck = 26, wAcct = 14;
    const rest = width - wSev - wCheck - wAcct - 8;
    const wRes = Math.max(18, Math.floor(rest * 0.38));
    const wTitle = rest - wRes;
    lines.push(c(DIM, [cut("SEVERITY", wSev), cut("CHECK", wCheck), cut("ACCOUNT", wAcct), cut("RESOURCE", wRes), "FINDING"].join("  ")));
    for (const f of findings) {
      lines.push([c(COLORS[f.severity], cut(f.severity.toUpperCase(), wSev)), cut(f.check, wCheck), cut(f.account, wAcct), cut(f.resource, wRes), cut(f.title, wTitle).trimEnd()].join("  "));
      lines.push(c(DIM, `${" ".repeat(wSev + 2)}fix: ${f.fix}`));
    }
  }
  lines.push("");
  lines.push(
    "Summary: " + Object.entries(r.summary).filter(([, n]) => n > 0).map(([s, n]) => c(COLORS[s], `${n} ${s}`)).join(", ") || "Summary: clean"
  );
  if (r.gaps.length) {
    lines.push("");
    lines.push(`Not checked (${r.gaps.length}):`);
    for (const g of r.gaps) lines.push(`  ${g.account}: ${g.what} — ${g.reason}`);
  }
  return lines.join("\n") + "\n";
}

// src/node/config.ts
import { readFile } from "node:fs/promises";
var KEYS = /* @__PURE__ */ new Set(["publicHostnames", "appAuthScripts", "staleDays", "compatMonths", "accounts", "tokenEnv", "repos", "authMarkers", "failOn", "$schema", "//"]);
function validateConfig(raw, file) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error(`${file}: expected a JSON object`);
  const o = raw;
  if ("token" in o || "apiToken" in o) throw new Error(`${file}: put tokens in environment variables and list their names in tokenEnv`);
  for (const k of Object.keys(o)) if (!KEYS.has(k)) throw new Error(`${file}: unknown key "${k}"`);
  const strs = (k) => {
    if (o[k] !== void 0 && (!Array.isArray(o[k]) || !o[k].every((x) => typeof x === "string"))) throw new Error(`${file}: ${k} must be an array of strings`);
  };
  ["publicHostnames", "appAuthScripts", "accounts", "tokenEnv", "repos"].forEach(strs);
  for (const k of ["staleDays", "compatMonths"]) if (o[k] !== void 0 && (typeof o[k] !== "number" || o[k] <= 0)) throw new Error(`${file}: ${k} must be a positive number`);
  if (o.authMarkers !== void 0) {
    const m = o.authMarkers;
    if (!Array.isArray(m) || !m.every((x) => x && typeof x.label === "string" && typeof x.pattern === "string")) throw new Error(`${file}: authMarkers must be [{ "label", "pattern" }]`);
    for (const x of m) new RegExp(x.pattern, "i");
  }
  return o;
}
async function loadConfig(file, required) {
  if (!file) return {};
  let text;
  try {
    text = await readFile(file, "utf8");
  } catch {
    if (required) throw new Error(`config file not found: ${file}`);
    return {};
  }
  return validateConfig(JSON.parse(text), file);
}

// src/node/scan.ts
import { readdir, readFile as readFile2, stat } from "node:fs/promises";
import { homedir } from "node:os";
import { basename, dirname, join, relative, resolve } from "node:path";

// src/core/wrangler.ts
function parseJsonc(text) {
  let out = "";
  let i = 0;
  while (i < text.length) {
    const c = text[i];
    if (c === '"') {
      const start = i++;
      while (i < text.length && text[i] !== '"') i += text[i] === "\\" ? 2 : 1;
      out += text.slice(start, ++i);
    } else if (c === "/" && text[i + 1] === "/") {
      while (i < text.length && text[i] !== "\n") i++;
    } else if (c === "/" && text[i + 1] === "*") {
      i = text.indexOf("*/", i + 2);
      i = i < 0 ? text.length : i + 2;
    } else {
      out += c;
      i++;
    }
  }
  return JSON.parse(out.replace(/,(\s*[}\]])/g, "$1"));
}
var FORBIDDEN_KEYS = /* @__PURE__ */ new Set(["__proto__", "constructor", "prototype"]);
var table = () => /* @__PURE__ */ Object.create(null);
function parseToml(text) {
  const root = table();
  let current = root;
  let i = 0;
  const n = text.length;
  const ws = () => {
    while (i < n && (text[i] === " " || text[i] === "	")) i++;
  };
  const wsNl = () => {
    for (; ; ) {
      while (i < n && /\s/.test(text[i])) i++;
      if (text[i] === "#") while (i < n && text[i] !== "\n") i++;
      else break;
    }
  };
  const fail = (msg) => {
    const line = text.slice(0, i).split("\n").length;
    throw new Error(`TOML line ${line}: ${msg}`);
  };
  const parseString = () => {
    const q = text[i];
    const triple = text.startsWith(q.repeat(3), i);
    if (triple) {
      i += 3;
      if (text[i] === "\n") i++;
      const end = text.indexOf(q.repeat(3), i);
      if (end < 0) fail("unterminated multi-line string");
      const s2 = text.slice(i, end);
      i = end + 3;
      return q === '"' ? unescape(s2) : s2;
    }
    i++;
    let s = "";
    while (i < n && text[i] !== q) {
      if (text[i] === "\n") fail("newline in string");
      if (q === '"' && text[i] === "\\") {
        s += text.slice(i, i + 2);
        i += 2;
      } else s += text[i++];
    }
    if (text[i] !== q) fail("unterminated string");
    i++;
    return q === '"' ? unescape(s) : s;
  };
  const unescape = (s) => s.replace(/\\(u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|.)/g, (_, e) => {
    if (e[0] === "u" || e[0] === "U") return String.fromCodePoint(parseInt(e.slice(1), 16));
    return { n: "\n", t: "	", r: "\r", '"': '"', "\\": "\\", b: "\b", f: "\f" }[e] ?? e;
  });
  const parseKey = () => {
    const parts = [];
    for (; ; ) {
      ws();
      if (text[i] === '"' || text[i] === "'") parts.push(parseString());
      else {
        const m = /^[A-Za-z0-9_-]+/.exec(text.slice(i));
        if (!m) fail("expected a key");
        parts.push(m[0]);
        i += m[0].length;
      }
      if (FORBIDDEN_KEYS.has(parts[parts.length - 1])) fail(`forbidden key "${parts[parts.length - 1]}"`);
      ws();
      if (text[i] === ".") i++;
      else return parts;
    }
  };
  const parseValue = () => {
    ws();
    const c = text[i];
    if (c === '"' || c === "'") return parseString();
    if (c === "[") {
      i++;
      const arr = [];
      for (; ; ) {
        wsNl();
        if (text[i] === "]") {
          i++;
          return arr;
        }
        arr.push(parseValue());
        wsNl();
        if (text[i] === ",") i++;
        else if (text[i] !== "]") fail("expected , or ] in array");
      }
    }
    if (c === "{") {
      i++;
      const obj = table();
      ws();
      if (text[i] === "}") {
        i++;
        return obj;
      }
      for (; ; ) {
        const key = parseKey();
        if (text[i] !== "=") fail("expected = in inline table");
        i++;
        setPath(obj, key, parseValue());
        ws();
        if (text[i] === ",") i++;
        else if (text[i] === "}") {
          i++;
          return obj;
        } else fail("expected , or } in inline table");
      }
    }
    const m = /^[^\s,\]}#]+/.exec(text.slice(i));
    if (!m) fail("expected a value");
    const raw = m[0];
    i += raw.length;
    if (raw === "true") return true;
    if (raw === "false") return false;
    if (/^[+-]?(\d[\d_]*)(\.\d+)?([eE][+-]?\d+)?$/.test(raw)) return Number(raw.replace(/_/g, ""));
    return raw;
  };
  const descend = (o, k) => {
    if (!Object.hasOwn(o, k)) o[k] = table();
    const next = Array.isArray(o[k]) ? o[k][o[k].length - 1] : o[k];
    if (next === null || typeof next !== "object") fail(`key "${k}" is not a table`);
    return next;
  };
  const setPath = (obj, path, value) => {
    let o = obj;
    for (const k of path.slice(0, -1)) o = descend(o, k);
    o[path[path.length - 1]] = value;
  };
  const tableAt = (path, arrayTable) => {
    let o = root;
    path.forEach((k, idx) => {
      const last = idx === path.length - 1;
      if (last && arrayTable) {
        if (!Object.hasOwn(o, k) || !Array.isArray(o[k])) o[k] = [];
        const t = table();
        o[k].push(t);
        o = t;
        return;
      }
      o = descend(o, k);
    });
    return o;
  };
  for (; ; ) {
    wsNl();
    if (i >= n) break;
    if (text[i] === "[") {
      const arrayTable = text[i + 1] === "[";
      i += arrayTable ? 2 : 1;
      const path = parseKey();
      if (text[i] !== "]" || arrayTable && text[i + 1] !== "]") fail("expected ] after table name");
      i += arrayTable ? 2 : 1;
      current = tableAt(path, arrayTable);
      continue;
    }
    const key = parseKey();
    if (text[i] !== "=") fail("expected =");
    i++;
    setPath(current, key, parseValue());
    ws();
    if (text[i] === "#") while (i < n && text[i] !== "\n") i++;
    if (i < n && text[i] !== "\n" && text[i] !== "\r") fail("expected end of line");
  }
  return root;
}
function routesOf(cfg) {
  const list = [];
  if (cfg.route !== void 0) list.push(cfg.route);
  if (Array.isArray(cfg.routes)) list.push(...cfg.routes);
  return list.flatMap((r) => {
    if (typeof r === "string") return [{ pattern: r, customDomain: false }];
    if (r && typeof r === "object" && typeof r.pattern === "string") {
      return [{ pattern: r.pattern, customDomain: r.custom_domain === true }];
    }
    return [];
  });
}
function ratelimitsOf(cfg) {
  const out = [];
  for (const b of Array.isArray(cfg.ratelimits) ? cfg.ratelimits : []) {
    if (b?.namespace_id !== void 0) out.push({ binding: String(b.name ?? ""), namespaceId: String(b.namespace_id) });
  }
  for (const b of Array.isArray(cfg.unsafe?.bindings) ? cfg.unsafe.bindings : []) {
    if (b?.type === "ratelimit" && b.namespace_id !== void 0) out.push({ binding: String(b.name ?? ""), namespaceId: String(b.namespace_id) });
  }
  return out;
}
var bool = (v) => typeof v === "boolean" ? v : void 0;
function cronsOf(c) {
  const list = c?.triggers?.crons;
  return Array.isArray(list) ? list.filter((x) => typeof x === "string") : void 0;
}
function workersFromConfig(cfg, file, authMarkers = []) {
  const name = typeof cfg.name === "string" ? cfg.name : void 0;
  if (!name) return [];
  const make = (c, workerName, env, parent) => {
    const routes = routesOf(c);
    const inherited = parent && routes.length === 0 && c.route === void 0 && c.routes === void 0 ? routesOf(parent) : routes;
    const workersDev = bool(c.workers_dev) ?? (parent ? bool(parent.workers_dev) : void 0);
    const previewUrls = bool(c.preview_urls) ?? (parent ? bool(parent.preview_urls) : void 0);
    const compat = c.compatibility_date ?? parent?.compatibility_date;
    const crons = cronsOf(c) ?? cronsOf(parent);
    return {
      name: workerName,
      file,
      ...env ? { env } : {},
      ...compat ? { compatibilityDate: String(compat) } : {},
      ...workersDev !== void 0 ? { workersDev } : {},
      ...previewUrls !== void 0 ? { previewUrls } : {},
      routes: inherited,
      ratelimitNamespaces: ratelimitsOf(c),
      authMarkers,
      ...crons?.length ? { crons } : {}
    };
  };
  const out = [make(cfg, name)];
  if (cfg.env && typeof cfg.env === "object") {
    for (const [env, ec] of Object.entries(cfg.env)) {
      if (!ec || typeof ec !== "object") continue;
      out.push(make(ec, typeof ec.name === "string" ? ec.name : `${name}-${env}`, env, cfg));
    }
  }
  return out;
}
function parseWranglerFile(file, text, authMarkers = []) {
  const cfg = file.endsWith(".toml") ? parseToml(text) : parseJsonc(text);
  return workersFromConfig(cfg, file, authMarkers);
}
var DEFAULT_AUTH_MARKERS = [
  { label: "Access JWT check", pattern: "cf-access-jwt-assertion" },
  { label: "passkey / WebAuthn", pattern: "navigator\\.credentials|webauthn|passkey" },
  { label: "sign-in route", pattern: "['\"`]/(login|signin|sign-in|auth/callback)['\"`/]" },
  { label: "email allowlist", pattern: "allowed_emails" },
  { label: "basic auth", pattern: "www-authenticate" }
];

// src/node/scan.ts
var CONFIG_NAMES = ["wrangler.jsonc", "wrangler.json", "wrangler.toml"];
var SKIP_DIRS = /* @__PURE__ */ new Set(["node_modules", ".git", "dist", "build", ".wrangler", ".next", ".turbo", "coverage", ".venv", "vendor"]);
var SOURCE_EXT = /\.(ts|tsx|js|mjs|jsx|cjs)$/;
var MAX_DEPTH = 4;
var MAX_SOURCE_FILES = 800;
var MAX_FILE_BYTES = 1e6;
function expandHome(p) {
  return p === "~" ? homedir() : p.startsWith("~/") ? join(homedir(), p.slice(2)) : p;
}
async function expandRepoArgs(args) {
  const out = [];
  for (const raw of args) {
    const p = resolve(expandHome(raw));
    if (basename(p) === "*") {
      const parent = dirname(p);
      try {
        for (const e of await readdir(parent, { withFileTypes: true })) if (e.isDirectory() && !e.name.startsWith(".")) out.push(join(parent, e.name));
      } catch {
      }
    } else out.push(p);
  }
  return [...new Set(out)];
}
async function findConfigs(dir, depth = 0) {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return [];
  }
  const found = [];
  const here = CONFIG_NAMES.find((n) => entries.some((e) => e.isFile() && e.name === n));
  if (here) found.push(join(dir, here));
  if (depth >= MAX_DEPTH) return found;
  for (const e of entries) {
    if (e.isDirectory() && !SKIP_DIRS.has(e.name) && !e.name.startsWith(".")) found.push(...await findConfigs(join(dir, e.name), depth + 1));
  }
  return found;
}
async function sourceFiles(dir, acc = [], depth = 0) {
  if (acc.length >= MAX_SOURCE_FILES || depth > 8) return acc;
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return acc;
  }
  for (const e of entries) {
    if (acc.length >= MAX_SOURCE_FILES) break;
    const p = join(dir, e.name);
    if (e.isDirectory() && !SKIP_DIRS.has(e.name) && !e.name.startsWith(".")) await sourceFiles(p, acc, depth + 1);
    else if (e.isFile() && SOURCE_EXT.test(e.name) && !e.name.endsWith(".d.ts") && !/\.(test|spec)\./.test(e.name)) acc.push(p);
  }
  return acc;
}
var handlerRe = (name) => new RegExp(
  `(?:^|[\\s,{;])(?:async\\s+)?${name}\\s*(?:\\([^)]*\\)\\s*(?::\\s*[^{;=]+)?\\{|:\\s*(?:async\\s+)?(?:function\\b|\\(|[A-Za-z_$][\\w$.]*\\s*[,}\\n]))|[{,]\\s*${name}\\s*[,}]|addEventListener\\(\\s*['"\`]${name}['"\`]`,
  "m"
);
var FETCH_RE = handlerRe("fetch");
var SCHEDULED_RE = handlerRe("scheduled");
var OPAQUE_DEFAULT_RE = /export\s+default\s+(?!\{|class\b|async\b|function\b)[A-Za-z_$]/;
async function scanSource(dir, markers = DEFAULT_AUTH_MARKERS) {
  const res = markers.map((m) => ({ label: m.label, re: new RegExp(m.pattern, "i") }));
  const hit = /* @__PURE__ */ new Set();
  const entry = { fetch: false, scheduled: false, opaqueDefault: false };
  let read = 0;
  for (const f of await sourceFiles(dir)) {
    try {
      if ((await stat(f)).size > MAX_FILE_BYTES) continue;
      const text = await readFile2(f, "utf8");
      read++;
      for (const m of res) if (!hit.has(m.label) && m.re.test(text)) hit.add(m.label);
      entry.fetch ||= FETCH_RE.test(text);
      entry.scheduled ||= SCHEDULED_RE.test(text);
      entry.opaqueDefault ||= OPAQUE_DEFAULT_RE.test(text);
    } catch {
    }
  }
  return { markers: [...hit], ...read ? { entry } : {} };
}
async function scanRepos(repos, opts = {}) {
  const workers = [];
  const gaps = [];
  const files = [];
  const base = opts.base ?? homedir();
  for (const repo of await expandRepoArgs(repos)) {
    for (const file of await findConfigs(repo)) {
      const shown = relative(base, file).startsWith("..") ? file : `~/${relative(base, file)}`;
      files.push(shown);
      try {
        const text = await readFile2(file, "utf8");
        const src = await scanSource(dirname(file), opts.markers);
        workers.push(...parseWranglerFile(shown, text, src.markers).map((w) => ({ ...w, file: shown, ...src.entry ? { entry: src.entry } : {} })));
      } catch (e) {
        gaps.push({ account: "local", what: shown, reason: `could not parse: ${e instanceof Error ? e.message : String(e)}` });
      }
    }
  }
  if (repos.length && files.length === 0) gaps.push({ account: "local", what: repos.join(" "), reason: "no wrangler.jsonc, wrangler.json or wrangler.toml found" });
  return { workers, gaps, files };
}

// src/node/state.ts
import { mkdir, readFile as readFile3, writeFile } from "node:fs/promises";
import { dirname as dirname2 } from "node:path";
async function loadState(file) {
  try {
    const s = JSON.parse(await readFile3(file, "utf8"));
    return s.version === 1 && s.secrets && typeof s.secrets === "object" ? s : void 0;
  } catch {
    return void 0;
  }
}
async function saveState(file, secrets, now) {
  await mkdir(dirname2(file), { recursive: true });
  const s = { version: 1, savedAt: now.toISOString(), secrets };
  await writeFile(file, JSON.stringify(s, null, 2) + "\n", { mode: 384 });
}

// src/main.ts
var HELP = `${BRAND.fullName}: read-only audit of Cloudflare accounts and Workers.

Usage: ${BRAND.cli} [options] [--repos <dir>...]

Tokens are read from environment variables only (never from argv):
  CF_API_TOKEN or CLOUDFLARE_API_TOKEN by default, or every --token-env NAME given.

Options:
  --token-env NAME        Env var holding a token; repeat for several accounts/tokens
  --account ID            Only audit this account id (repeatable); default: all the token sees
  --repos DIR...          Scan wrangler.toml/json/jsonc under these dirs ("~/dev/*" works)
  --no-api                Local wrangler files only; no Cloudflare calls
  --config FILE           Config file (default ./flare.config.json if present)
  --public HOST           Hostname meant to be public (repeatable; "*.example.com" ok)
  --stale-days N          Dead-script threshold (default ${DEFAULT_OPTIONS.staleDays})
  --compat-months N       Old compatibility_date threshold (default ${DEFAULT_OPTIONS.compatMonths})
  --shallow               Skip per-script calls (faster; no workers.dev/bindings/secrets data)
  --json [FILE]           JSON to FILE, or to stdout instead of the table
  --html FILE             Write the self-contained HTML report
  --state FILE            Secret-name baseline (default ~/.${BRAND.cli}/state.json)
  --no-state              Do not read or write the baseline
  --snapshot-out FILE     Save the collected data (no secret values) for replay
  --snapshot-in FILE      Audit a saved snapshot instead of calling the API (as of its takenAt)
  --summary FILE          Append the findings as a Markdown table (CI job summary)
  --ingest-out FILE       Write the dawnfix.flare/1 counts document: counts per check and
                          severity and hashed account ids, no names (schema/flare-ingest.schema.json)
  --fail-on LEVEL         Exit 1 when a finding is at/above LEVEL: ${SEVERITIES.join("|")}|never (default high)
  --no-color              Plain table
  -h, --help              This help
`;
async function main(argv, io) {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      allowPositionals: true,
      options: {
        "token-env": { type: "string", multiple: true },
        account: { type: "string", multiple: true },
        repos: { type: "string", multiple: true },
        "no-api": { type: "boolean" },
        config: { type: "string" },
        public: { type: "string", multiple: true },
        "stale-days": { type: "string" },
        "compat-months": { type: "string" },
        shallow: { type: "boolean" },
        json: { type: "boolean" },
        html: { type: "string" },
        state: { type: "string" },
        "no-state": { type: "boolean" },
        "snapshot-out": { type: "string" },
        "snapshot-in": { type: "string" },
        summary: { type: "string" },
        "ingest-out": { type: "string" },
        "fail-on": { type: "string" },
        "no-color": { type: "boolean" },
        help: { type: "boolean", short: "h" }
      }
    });
  } catch (e) {
    io.stderr(`${e instanceof Error ? e.message : String(e)}

${HELP}`);
    return 2;
  }
  const v = parsed.values;
  if (v.help) {
    io.stdout(HELP);
    return 0;
  }
  let jsonFile;
  const positionals = [...parsed.positionals];
  if (v.json) {
    const at = argv.indexOf("--json");
    const next = argv[at + 1];
    if (next && !next.startsWith("-") && next.endsWith(".json") && positionals.includes(next)) {
      jsonFile = next;
      positionals.splice(positionals.indexOf(next), 1);
    }
  }
  try {
    const defaultConfig = join2(io.cwd, "flare.config.json");
    const cfgFile = v.config ? resolve2(io.cwd, expandHome(v.config)) : existsSync(defaultConfig) ? defaultConfig : void 0;
    const cfg = await loadConfig(cfgFile, Boolean(v.config));
    const failOn = v["fail-on"] ?? cfg.failOn ?? "high";
    if (failOn !== "never" && !SEVERITIES.includes(failOn)) throw new Error(`--fail-on must be one of ${SEVERITIES.join(", ")}, never`);
    const num = (s, d, name) => {
      if (s === void 0) return d;
      const n = Number(s);
      if (!Number.isFinite(n) || n <= 0) throw new Error(`${name} must be a positive number`);
      return n;
    };
    let now = io.now();
    const repos = [...v.repos ?? [], ...positionals, ...v.repos || positionals.length ? [] : cfg.repos ?? []];
    let snapshot;
    if (v["snapshot-in"]) {
      snapshot = JSON.parse(await readFile4(resolve2(io.cwd, v["snapshot-in"]), "utf8"));
      const taken = new Date(snapshot.takenAt);
      if (!Number.isNaN(taken.getTime())) now = taken;
    } else {
      const local = repos.length ? await scanRepos(repos, cfg.authMarkers ? { markers: cfg.authMarkers } : {}) : { workers: [], gaps: [], files: [] };
      const tokenEnv = v["token-env"] ?? cfg.tokenEnv ?? ["CF_API_TOKEN", "CLOUDFLARE_API_TOKEN"];
      const tokens = v["no-api"] ? [] : [...new Set(tokenEnv.map((n) => io.env[n]).filter((t) => Boolean(t)))];
      if (!v["no-api"] && tokens.length === 0) {
        if (!repos.length) throw new Error(`no token: set ${tokenEnv.join(" or ")}, or pass --no-api with --repos`);
        io.stderr(`No token in ${tokenEnv.join("/")}; auditing local files only.
`);
      }
      const accountIds = v.account ?? cfg.accounts;
      const collected = await collectSnapshot({
        tokens,
        fetch: io.fetch,
        local: local.workers,
        collect: { ...accountIds?.length ? { accountIds } : {}, ...v.shallow ? { shallow: true } : {} },
        now
      });
      snapshot = collected.snapshot;
      snapshot.localGaps.push(...local.gaps);
    }
    if (v["snapshot-out"]) await writeFile2(resolve2(io.cwd, v["snapshot-out"]), JSON.stringify(snapshot, null, 2) + "\n", { mode: 384 });
    const stateFile = resolve2(io.cwd, expandHome(v.state ?? join2(homedir2(), `.${BRAND.cli}`, "state.json")));
    const useState = !v["no-state"] && !v["snapshot-in"];
    const prev = useState ? await loadState(stateFile) : void 0;
    const { result, secretsBaseline } = audit(snapshot, {
      publicHostnames: [...cfg.publicHostnames ?? [], ...v.public ?? []],
      appAuthScripts: cfg.appAuthScripts ?? [],
      staleDays: num(v["stale-days"], cfg.staleDays ?? DEFAULT_OPTIONS.staleDays, "--stale-days"),
      compatMonths: num(v["compat-months"], cfg.compatMonths ?? DEFAULT_OPTIONS.compatMonths, "--compat-months"),
      ...prev ? { secretsBaseline: prev.secrets } : {},
      now
    });
    if (useState && Object.keys(secretsBaseline).length) await saveState(stateFile, secretsBaseline, now);
    if (v.html) {
      await writeFile2(resolve2(io.cwd, v.html), renderHtml(result));
      io.stderr(`HTML report: ${resolve2(io.cwd, v.html)}
`);
    }
    if (v.summary) await appendFile(resolve2(io.cwd, v.summary), renderMarkdown(result));
    if (v["ingest-out"]) await writeFile2(resolve2(io.cwd, v["ingest-out"]), JSON.stringify(await ingestDoc(result), null, 2) + "\n");
    const json = JSON.stringify({ ...result, pitch: BRAND.pitch }, null, 2) + "\n";
    if (v.json && jsonFile) await writeFile2(resolve2(io.cwd, jsonFile), json);
    if (v.json && !jsonFile) io.stdout(json);
    else io.stdout(renderText(result, { color: io.isTTY && !v["no-color"] && !io.env.NO_COLOR, ...io.columns ? { width: io.columns } : {} }));
    return failsAt(result, failOn) ? 1 : 0;
  } catch (e) {
    io.stderr(`${BRAND.cli}: ${e instanceof Error ? e.message : String(e)}
`);
    return 2;
  }
}

// src/cli.ts
var invoked = process.argv[1] && existsSync2(process.argv[1]) ? pathToFileURL(realpathSync(process.argv[1])).href : "";
if (import.meta.url === invoked) {
  main(process.argv.slice(2), {
    env: process.env,
    fetch: globalThis.fetch,
    stdout: (s) => process.stdout.write(s),
    stderr: (s) => process.stderr.write(s),
    now: () => /* @__PURE__ */ new Date(),
    isTTY: Boolean(process.stdout.isTTY),
    ...process.stdout.columns ? { columns: process.stdout.columns } : {},
    cwd: process.cwd()
  }).then((code) => process.exit(code));
}
export {
  HELP,
  main
};
