// One self-contained HTML file: inline CSS and a few lines of inline JS for the severity
// filter, no external fonts, scripts or images. Light and dark follow the system; cards
// stack on a phone. Every value from Cloudflare or a config file is escaped. The look is the
// document style (green Tech-Azur) the Dawnfix site's docs and sample pages use: DOC_STYLE,
// plus the few rules only this report needs.

import { BRAND } from '../brand.js';
import { DOC_STYLE } from './doc-style.js';
import { SEVERITIES, type AuditResult, type CheckId, type Severity } from '../types.js';

export const esc = (s: unknown): string =>
  String(s).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]!);

export const CHECK_NAMES: Record<CheckId, string> = {
  'workers-dev-enabled': 'workers.dev exposure',
  'preview-urls-enabled': 'Preview URLs',
  'hostname-without-auth': 'Hostname without auth',
  'ratelimit-namespace-shared': 'Rate-limit namespace clash',
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

/** Each severity as a status pill of the document style: its meaning kept, worst first. */
export const SEVERITY_PILL: Record<Severity, string> = {
  critical: 'pri p0',
  high: 'pill crit',
  medium: 'pill weak',
  low: 'pill mixed',
  info: 'pill unknown',
};

const REPORT_CSS = `
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

export function renderHtml(r: AuditResult): string {
  const counts = SEVERITIES.map((s) => [s, r.summary[s]] as [Severity, number]);
  const rows = r.findings
    .map(
      (f) => `<li class="f" data-sev="${f.severity}">
  <div class="head"><span class="${SEVERITY_PILL[f.severity]}">${esc(f.severity)}</span><span class="chk">${esc(CHECK_NAMES[f.check] ?? f.check)}</span><span class="end acct">${esc(f.account)} · ${esc(f.source)}</span></div>
  <code class="res">${esc(f.resource)}</code>
  <div class="title">${esc(f.title)}</div>
  <p class="detail">${esc(f.detail)}</p>
  <p class="fix"><b>Fix</b> ${esc(f.fix)}</p>
</li>`,
    )
    .join('\n');
  const gaps = r.gaps.length
    ? `<h2>Not checked</h2><p class="muted">These parts could not be read with the token given, so their checks did not run.</p><ul class="gaps">${r.gaps
        .map((g) => `<li><b>${esc(g.account)}</b> ${esc(g.what)} <span class="muted">— ${esc(g.reason)}</span></li>`)
        .join('')}</ul>`
    : '';
  const accounts = r.accounts.map((a) => `<tr><td>${esc(a.name)}</td><td class="n">${esc(a.scripts)}</td><td class="n">${esc(a.zones)}</td></tr>`).join('');

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
<p class="meta">${esc(r.generatedAt.slice(0, 16).replace('T', ' '))} UTC · ${esc(r.accounts.length)} account(s) · ${esc(r.localFiles)} local wrangler file(s) · read-only</p>
<h2>Findings</h2>
<div class="chips" role="group" aria-label="Filter by severity">
${counts.map(([s, n]) => `<button class="chip" type="button" aria-pressed="true" data-filter="${s}"><span class="${SEVERITY_PILL[s]}">${s}</span> <b>${n}</b></button>`).join('\n')}
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
