// Who can reach a Worker: workers.dev and preview URLs (hostnames outside every zone's WAF,
// rate-limit rules and Access), and custom hostnames with no sign-in in front of them.

import { accessCoverage, hostMatches } from '../hosts.js';
import type { CfAccessApp, Finding, LocalWorker } from '../types.js';
import { label, type Ctx } from './context.js';

const WD_FIX = 'Set "workers_dev": false in the wrangler config and redeploy (or Worker > Settings > Domains & Routes > workers.dev > Disable).';
const PV_FIX = 'Set "preview_urls": false in the wrangler config and redeploy (or Worker > Settings > Domains & Routes > Preview URLs > Disable).';

const servesHttp = (handlers: string[]) => handlers.length === 0 || handlers.includes('fetch');

/**
 * A Worker whose source shows a scheduled handler (or whose config has cron triggers) and no
 * fetch handler, and no default export the text search cannot see into. workers.dev on such
 * a Worker answers every request with an error, so the exposure is low.
 */
export function cronOnly(w: LocalWorker): boolean {
  if (!w.entry) return false;
  return (w.entry.scheduled || (w.crons?.length ?? 0) > 0) && !w.entry.fetch && !w.entry.opaqueDefault;
}

/** workers_dev as wrangler resolves it: absent means true without routes, false with them. */
export function effectiveWorkersDev(w: LocalWorker): { value: boolean; explicit: boolean } {
  if (w.workersDev !== undefined) return { value: w.workersDev, explicit: true };
  return { value: w.routes.length === 0, explicit: false };
}

/**
 * Whether an Access application covers a workers.dev hostname: an `all_workers` or `worker`
 * destination, or a self-hosted app on that hostname or `*.<subdomain>.workers.dev` (what
 * "Enable Cloudflare Access" on workers.dev / Preview URLs creates).
 */
export function accessOnWorkersDev(apps: CfAccessApp[] | undefined, script: string, host: string | undefined): boolean {
  return (apps ?? []).some(
    (app) => app.allWorkers === true || (app.workers ?? []).includes(script) || (host !== undefined && app.domains.some((d) => accessCoverage(d, host) === 'full')),
  );
}

export function checkWorkersDev(ctx: Ctx): Finding[] {
  const out: Finding[] = [];
  const reported = new Set<string>();
  for (const a of ctx.accounts) {
    for (const s of a.snap.scripts ?? []) {
      const lw = a.local.get(s.name);
      const hosts = a.hostsByScript.get(s.name);
      const sub = a.snap.workersSubdomain;
      const url = sub ? `${s.name}.${sub}.workers.dev` : `${s.name}.<subdomain>.workers.dev`;
      const ACCESS = ' An Access application covers it, so a visitor must sign in first.';
      if (s.subdomain?.enabled) {
        reported.add(s.name);
        const hasHosts = (hosts?.size ?? 0) > 0;
        const guarded = accessOnWorkersDev(a.snap.accessApps, s.name, sub ? url : undefined);
        out.push({
          check: 'workers-dev-enabled',
          severity: !servesHttp(s.handlers) || guarded ? 'low' : hasHosts ? 'high' : 'medium',
          account: label(a.snap),
          resource: s.name,
          title: (hasHosts ? 'Reachable on workers.dev, around its custom domain' : 'Public on workers.dev') + (guarded ? ' (behind Access)' : ''),
          detail:
            (hasHosts
              ? `${url} serves the same Worker as ${[...hosts!].join(', ')}, but outside that zone's WAF, rate-limiting rules${guarded ? '' : ' and Access'}.`
              : `${url} is this Worker's only public address; no zone rules apply to it.`) + (guarded ? ACCESS : ''),
          fix: hasHosts ? WD_FIX : `Give it a custom domain, then: ${WD_FIX}`,
          source: lw && !effectiveWorkersDev(lw).explicit ? 'api+local' : 'api',
        });
      }
      if (s.subdomain?.previewsEnabled) {
        reported.add(`preview:${s.name}`);
        // Preview hostnames are <version prefix>-<script>.<subdomain>.workers.dev.
        const guarded = accessOnWorkersDev(a.snap.accessApps, s.name, sub ? `00000000-${url}` : undefined);
        out.push({
          check: 'preview-urls-enabled',
          severity: servesHttp(s.handlers) && !guarded ? 'medium' : 'low',
          account: label(a.snap),
          resource: s.name,
          title: 'Preview URLs enabled' + (guarded ? ' (behind Access)' : ''),
          detail: `Every uploaded version gets its own public <version>-${url} address, with no zone rules in front.` + (guarded ? ACCESS : ''),
          fix: PV_FIX,
          source: lw && lw.previewUrls === undefined ? 'api+local' : 'api',
        });
      }
    }
  }
  // Local files: catch it before the next deploy turns it on.
  for (const w of ctx.snap.local) {
    const wd = effectiveWorkersDev(w);
    if (!reported.has(w.name)) {
      if (wd.value) {
        const cron = cronOnly(w);
        out.push({
          check: 'workers-dev-enabled',
          severity: cron ? 'low' : 'medium',
          account: 'local',
          resource: w.name,
          title: wd.explicit ? 'workers_dev is true in config' : 'workers_dev not set and no routes, so it defaults to on',
          detail:
            `${w.file}${w.env ? ` [env.${w.env}]` : ''}: the next deploy publishes this Worker on workers.dev.` +
            (cron ? ' The source shows a scheduled handler and no fetch handler, so the address would only answer with an error.' : ''),
          fix: WD_FIX,
          source: 'local',
        });
      } else if (!wd.explicit) {
        out.push({
          check: 'workers-dev-enabled',
          severity: 'info',
          account: 'local',
          resource: w.name,
          title: 'workers_dev not set explicitly',
          detail: `${w.file}${w.env ? ` [env.${w.env}]` : ''}: off today only because routes exist; removing the routes turns workers.dev on.`,
          fix: 'Add "workers_dev": false.',
          source: 'local',
        });
      }
    }
    if (!reported.has(`preview:${w.name}`)) {
      if (w.previewUrls === true || (w.previewUrls === undefined && wd.value)) {
        out.push({
          check: 'preview-urls-enabled',
          severity: w.previewUrls === true ? 'medium' : 'low',
          account: 'local',
          resource: w.name,
          title: w.previewUrls === true ? 'preview_urls is true in config' : 'preview_urls not set; it follows workers_dev, which is on',
          detail: `${w.file}${w.env ? ` [env.${w.env}]` : ''}`,
          fix: PV_FIX,
          source: 'local',
        });
      } else if (w.previewUrls === undefined) {
        out.push({
          check: 'preview-urls-enabled',
          severity: 'info',
          account: 'local',
          resource: w.name,
          title: 'preview_urls not set explicitly',
          detail: `${w.file}${w.env ? ` [env.${w.env}]` : ''}: wrangler leaves an existing setting unchanged when the key is absent.`,
          fix: 'Add "preview_urls": false.',
          source: 'local',
        });
      }
    }
  }
  return out;
}

export function isPublicByPolicy(ctx: Ctx, host: string): boolean {
  return ctx.opts.publicHostnames.some((rule) => hostMatches(rule, host));
}

export function checkHostnameAuth(ctx: Ctx): Finding[] {
  const out: Finding[] = [];
  for (const a of ctx.accounts) {
    const apps = a.snap.accessApps;
    for (const [script, hosts] of a.hostsByScript) {
      if (!a.scriptNames.has(script)) continue; // reported by route-to-missing-script
      const lw = a.local.get(script);
      const appAuth = ctx.opts.appAuthScripts.includes(script) || (lw?.authMarkers.length ?? 0) > 0;
      for (const host of hosts) {
        if (isPublicByPolicy(ctx, host) || appAuth) continue;
        const coverage = apps?.map((app) => app.domains.map((d) => accessCoverage(d, host))).flat() ?? [];
        if (coverage.includes('full')) continue;
        const partial = coverage.includes('partial');
        out.push({
          check: 'hostname-without-auth',
          severity: apps === undefined ? 'low' : partial ? 'low' : 'medium',
          account: label(a.snap),
          resource: host,
          title: partial ? 'Access covers only some paths' : 'No Access application and no app sign-in found',
          detail:
            `Served by ${script}. ` +
            (apps === undefined
              ? 'Access applications could not be read, so this is unverified. '
              : partial
                ? 'An Access app matches this host on a sub-path only. '
                : 'No Access application matches this hostname. ') +
            (lw ? 'The repo shows no sign-in marker.' : 'No local repo was scanned for this Worker, so app-level sign-in is unknown.'),
          fix: `If it is meant to be public, add "${host}" to publicHostnames. Otherwise put a self-hosted Access application on it, or list the script in appAuthScripts if it signs users in itself.`,
          source: lw ? 'api+local' : 'api',
        });
      }
    }
  }
  // Workers only seen locally: no Access data at all, so report quietly.
  for (const w of ctx.unmatchedLocal) {
    if (w.authMarkers.length > 0 || ctx.opts.appAuthScripts.includes(w.name)) continue;
    for (const r of w.routes) {
      const host = r.pattern.split('/')[0]!.toLowerCase();
      if (isPublicByPolicy(ctx, host)) continue;
      out.push({
        check: 'hostname-without-auth',
        severity: 'info',
        account: 'local',
        resource: host,
        title: 'No sign-in marker in the repo (Access not checked)',
        detail: `${w.file}: route for ${w.name}; no API data matched this Worker, so Access was not checked.`,
        fix: `Add "${host}" to publicHostnames if public; otherwise check it has an Access application.`,
        source: 'local',
      });
    }
  }
  return out;
}
