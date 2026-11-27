// Routes and DNS that point at nothing: a route or custom domain whose script is gone, a
// CNAME into workers.dev or a sibling zone where the target no longer exists, and the
// placeholder records that only existed to carry a Workers route that has since gone.

import { hostMatches, hostOf } from '../hosts.js';
import type { Finding } from '../types.js';
import { label, type Ctx } from './context.js';

export function checkRoutesToMissingScripts(ctx: Ctx): Finding[] {
  const out: Finding[] = [];
  for (const a of ctx.accounts) {
    if (!a.snap.scripts) continue; // cannot tell missing from unreadable
    for (const z of a.snap.zones ?? []) {
      for (const r of z.routes ?? []) {
        if (r.script && !a.scriptNames.has(r.script)) {
          out.push({
            check: 'route-to-missing-script',
            severity: 'high',
            account: label(a.snap),
            resource: r.pattern,
            title: `Route points at deleted Worker "${r.script}"`,
            detail: `Zone ${z.name}, route id ${r.id}. Requests here get an error, and a new script with that name would take the route over.`,
            fix: `Delete the route (zone ${z.name} > Workers Routes), or redeploy "${r.script}" if it should exist.`,
            source: 'api',
          });
        }
      }
    }
    for (const d of a.snap.customDomains ?? []) {
      if (!a.scriptNames.has(d.service)) {
        out.push({
          check: 'route-to-missing-script',
          severity: 'high',
          account: label(a.snap),
          resource: d.hostname,
          title: `Custom domain bound to missing Worker "${d.service}"`,
          detail: `Zone ${d.zoneName ?? d.zoneId ?? '?'}.`,
          fix: `Detach the custom domain, or redeploy "${d.service}".`,
          source: 'api',
        });
      }
    }
  }
  return out;
}

// Origin addresses used only so a proxied record exists for a Workers route.
const PLACEHOLDER_A = /^192\.0\.2\.\d+$/;
const PLACEHOLDER_AAAA = /^100::(0)?$/i;

export function checkDanglingDns(ctx: Ctx): Finding[] {
  const out: Finding[] = [];
  for (const a of ctx.accounts) {
    const zones = a.snap.zones ?? [];
    const routeHosts = zones.flatMap((z) => (z.routes ?? []).filter((r) => r.script).map((r) => hostOf(r.pattern)));
    const customHosts = new Set((a.snap.customDomains ?? []).map((d) => d.hostname.toLowerCase()));
    const namesByZone = new Map(zones.filter((z) => z.dns).map((z) => [z.name.toLowerCase(), new Set(z.dns!.map((r) => r.name.toLowerCase()))]));
    const scripts = new Map((a.snap.scripts ?? []).map((s) => [s.name, s]));

    for (const z of zones) {
      for (const rec of z.dns ?? []) {
        const name = rec.name.toLowerCase();
        const target = rec.content.toLowerCase().replace(/\.$/, '');
        if (rec.type === 'CNAME' && target.endsWith('.workers.dev') && a.snap.scripts) {
          const [script, sub] = target.split('.');
          const s = script ? scripts.get(script) : undefined;
          const otherSub = a.snap.workersSubdomain && sub !== a.snap.workersSubdomain.toLowerCase();
          if (otherSub || !s || s.subdomain?.enabled === false) {
            out.push({
              check: 'dangling-dns',
              severity: otherSub ? 'medium' : 'high',
              account: label(a.snap),
              resource: name,
              title: otherSub ? 'CNAME into a different workers.dev subdomain' : !s ? `CNAME to workers.dev for missing Worker "${script}"` : `CNAME to "${script}" on workers.dev, which is disabled`,
              detail: `${z.name}: ${name} CNAME ${target}.${otherSub ? ` This account's subdomain is ${a.snap.workersSubdomain}; the target belongs to another account or a renamed subdomain.` : ''}`,
              fix: 'Delete the record, or replace it with a Workers custom domain on the script it should serve.',
              source: 'api',
            });
          }
          continue;
        }
        if (rec.type === 'CNAME') {
          const zoneOfTarget = [...namesByZone.keys()].find((zn) => target === zn || target.endsWith(`.${zn}`));
          if (zoneOfTarget && !namesByZone.get(zoneOfTarget)!.has(target) && !customHosts.has(target)) {
            const wildcard = [...namesByZone.get(zoneOfTarget)!].some((n) => n.startsWith('*.') && hostMatches(n, target));
            if (!wildcard) {
              out.push({
                check: 'dangling-dns',
                severity: 'medium',
                account: label(a.snap),
                resource: name,
                title: 'CNAME to a name that no longer exists',
                detail: `${z.name}: ${name} CNAME ${target}, and zone ${zoneOfTarget} has no record for ${target}.`,
                fix: 'Delete the record, or recreate its target.',
                source: 'api',
              });
            }
          }
          continue;
        }
        const placeholder = (rec.type === 'A' && PLACEHOLDER_A.test(target)) || (rec.type === 'AAAA' && PLACEHOLDER_AAAA.test(target));
        if (placeholder && a.snap.zones?.every((zz) => zz.routes !== undefined)) {
          const served = routeHosts.some((h) => hostMatches(h, name)) || customHosts.has(name);
          if (!served) {
            out.push({
              check: 'dangling-dns',
              severity: 'medium',
              account: label(a.snap),
              resource: name,
              title: 'Placeholder record with no Workers route',
              detail: `${z.name}: ${name} ${rec.type} ${rec.content}${rec.proxied ? ' (proxied)' : ''}. That address only exists to carry a Workers route, and no route matches it any more.`,
              fix: 'Delete the record, or add the route back.',
              source: 'api',
            });
          }
        }
      }
    }
  }
  return out;
}
