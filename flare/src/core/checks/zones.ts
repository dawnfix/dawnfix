// Zone-wide transport settings: minimum TLS, Always Use HTTPS, HSTS.

import type { Finding } from '../types.js';
import { label, type Ctx } from './context.js';

const HSTS_MIN_AGE = 15_552_000; // 180 days

export function checkZoneTls(ctx: Ctx): Finding[] {
  const out: Finding[] = [];
  for (const a of ctx.accounts) {
    for (const z of a.snap.zones ?? []) {
      if (z.status && z.status !== 'active') continue;
      const s = z.settings;
      if (!s) continue;
      const push = (severity: Finding['severity'], title: string, detail: string, fix: string) =>
        out.push({ check: 'zone-tls', severity, account: label(a.snap), resource: z.name, title, detail, fix, source: 'api' });
      if (s.minTlsVersion && Number(s.minTlsVersion) < 1.2) {
        push('medium', `Minimum TLS ${s.minTlsVersion}`, 'TLS 1.0 and 1.1 are deprecated and fail PCI DSS.', 'SSL/TLS > Edge Certificates > Minimum TLS Version: 1.2.');
      }
      if (s.alwaysUseHttps === 'off') {
        push('medium', 'Always Use HTTPS is off', 'Plain-HTTP requests are served instead of redirected.', 'SSL/TLS > Edge Certificates > Always Use HTTPS: on.');
      }
      if (s.hsts && !s.hsts.enabled) {
        push('low', 'HSTS off', 'Browsers will try plain HTTP first on every new visit.', 'SSL/TLS > Edge Certificates > HTTP Strict Transport Security: enable, max-age 6 months or more, once every subdomain serves HTTPS.');
      } else if (s.hsts && s.hsts.maxAge < HSTS_MIN_AGE) {
        push('low', `HSTS max-age ${s.hsts.maxAge}s`, 'Below 6 months, so it lapses for visitors who come back rarely.', 'Raise max-age to 15552000 or more.');
      }
    }
  }
  return out;
}
