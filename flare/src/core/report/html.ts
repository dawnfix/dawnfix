// One self-contained HTML file: inline CSS and a few lines of inline JS for the severity
// filter, no external fonts, scripts or images. Light and dark follow the system; cards
// stack on a phone. Every value from Cloudflare or a config file is escaped.

import { BRAND } from '../brand.js';
import { SEVERITIES, type AuditResult, type CheckId, type Severity } from '../types.js';

export const esc = (s: unknown): string =>
  String(s).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]!);

export const CHECK_NAMES: Record<CheckId, string> = {
  'workers-dev-enabled': 'workers.dev exposure',
  'preview-urls-enabled': 'Preview URLs',
  'hostname-without-auth': 'Hostname without auth',
  'ratelimit-namespace-shared': 'Ratelimit namespace clash',
  'route-to-missing-script': 'Route to missing Worker',
  'dangling-dns': 'Dangling DNS',
  'dead-script': 'Dead script',
  'compat-date-old': 'Old compatibility date',
  'secrets-changed': 'Secrets changed',
  'token-over-scoped': 'Over-scoped token',
  'token-no-expiry': 'Token never expires',
  'token-unused': 'Unused token',
  'zone-tls': 'Zone TLS / HSTS',
};

export function renderHtml(r: AuditResult): string {
  const counts = SEVERITIES.map((s) => [s, r.summary[s]] as [Severity, number]);
  const rows = r.findings
    .map(
      (f) => `<li class="f" data-sev="${f.severity}">
  <div class="top"><span class="sev ${f.severity}">${esc(f.severity)}</span><span class="chk">${esc(CHECK_NAMES[f.check] ?? f.check)}</span><span class="acct">${esc(f.account)} · ${esc(f.source)}</span></div>
  <div class="res">${esc(f.resource)}</div>
  <div class="title">${esc(f.title)}</div>
  <p class="detail">${esc(f.detail)}</p>
  <p class="fix"><b>Fix</b> ${esc(f.fix)}</p>
</li>`,
    )
    .join('\n');
  const gaps = r.gaps.length
    ? `<section><h2>Not checked</h2><p class="muted">These parts could not be read with the token given, so their checks did not run.</p><ul class="gaps">${r.gaps
        .map((g) => `<li><b>${esc(g.account)}</b> ${esc(g.what)} <span class="muted">— ${esc(g.reason)}</span></li>`)
        .join('')}</ul></section>`
    : '';
  const accounts = r.accounts.map((a) => `<li>${esc(a.name)} <span class="muted">${esc(a.scripts)} scripts · ${esc(a.zones)} zones</span></li>`).join('');

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>${esc(BRAND.product)} audit</title>
<style>
:root{--bg:#f7f6f3;--card:#fff;--fg:#1c1b19;--muted:#6b6862;--line:#e4e1da;--accent:#c2410c;
--critical:#7f1d1d;--critical-bg:#fde2e2;--high:#b42318;--high-bg:#fee4e2;--medium:#b54708;--medium-bg:#fef0c7;--low:#175cd3;--low-bg:#e0eaff;--info:#475467;--info-bg:#eaecf0}
@media (prefers-color-scheme:dark){:root{--bg:#141311;--card:#1d1c19;--fg:#ecebe8;--muted:#a09c94;--line:#2e2c28;--accent:#fb923c;
--critical:#fecaca;--critical-bg:#5f1414;--high:#fda29b;--high-bg:#55160c;--medium:#fec84b;--medium-bg:#4e2a06;--low:#84adff;--low-bg:#102a56;--info:#cfd4dc;--info-bg:#2a2f37}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:32px 0 8px}
.muted{color:var(--muted)}
header .brand{color:var(--accent);font-weight:600;letter-spacing:.02em;font-size:13px;text-transform:uppercase}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}
.chip{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:999px;padding:6px 12px;font:inherit;font-size:14px;cursor:pointer}
.chip[aria-pressed="false"]{opacity:.45}
.chip b{font-variant-numeric:tabular-nums}
ul{list-style:none;padding:0;margin:0}
.f{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}
.top{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-size:13px}
.sev{font-weight:700;text-transform:uppercase;font-size:11px;letter-spacing:.05em;padding:2px 8px;border-radius:6px}
${SEVERITIES.map((s) => `.sev.${s}{color:var(--${s});background:var(--${s}-bg)}`).join('')}
.chk{font-weight:600}.acct{color:var(--muted);margin-left:auto}
.res{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;margin-top:8px;overflow-wrap:anywhere}
.title{font-weight:600;margin-top:2px}
.detail{margin:6px 0;color:var(--muted);overflow-wrap:anywhere}
.fix{margin:6px 0 0;overflow-wrap:anywhere}.fix b{color:var(--accent);margin-right:4px}
.gaps li,.accts li{padding:6px 0;border-bottom:1px solid var(--line);overflow-wrap:anywhere}
footer{margin-top:40px;font-size:13px}
@media (max-width:560px){.acct{margin-left:0;width:100%}}
</style>
</head>
<body>
<main>
<header>
<div class="brand">${esc(BRAND.fullName)}</div>
<h1>Cloudflare account and Workers audit</h1>
<div class="muted">${esc(r.generatedAt.slice(0, 16).replace('T', ' '))} UTC · ${esc(r.accounts.length)} account(s) · ${esc(r.localFiles)} local wrangler file(s) · read-only</div>
</header>
<div class="chips" role="group" aria-label="Filter by severity">
${counts.map(([s, n]) => `<button class="chip" type="button" aria-pressed="true" data-filter="${s}"><span class="sev ${s}">${s}</span> <b>${n}</b></button>`).join('\n')}
</div>
${r.findings.length ? `<ul id="findings">${rows}</ul>` : '<p>No findings.</p>'}
${gaps}
<section><h2>Accounts</h2><ul class="accts">${accounts || '<li class="muted">None (local files only)</li>'}</ul></section>
<footer class="muted">${esc(BRAND.fullName)} · ${esc(BRAND.org)} · Generated with read-only API calls; secret values are never read.</footer>
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
