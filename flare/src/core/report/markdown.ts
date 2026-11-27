// The findings as GitHub-flavoured Markdown, for a CI job summary ($GITHUB_STEP_SUMMARY).
// This is where the names live in the daily CI audit: in the customer's GitHub, never sent
// anywhere else. Values from Cloudflare are escaped so a name cannot break the table or
// inject markup.

import { BRAND } from '../brand.js';
import { SEVERITIES, type AuditResult } from '../types.js';
import { CHECK_NAMES } from './html.js';

/** GitHub caps a step summary at 1 MiB; keep well under it. */
export const MAX_SUMMARY_ROWS = 300;

export const mdCell = (s: unknown): string =>
  String(s)
    .replace(/[\r\n]+/g, ' ')
    .replace(/\\/g, '\\\\')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/`/g, "'")
    .replace(/([*_[\]|])/g, '\\$1');

export function renderMarkdown(r: AuditResult): string {
  const counts = SEVERITIES.filter((s) => r.summary[s] > 0).map((s) => `${r.summary[s]} ${s}`);
  const lines = [
    `## ${BRAND.fullName}: Cloudflare audit`,
    '',
    `${r.generatedAt.slice(0, 16).replace('T', ' ')} UTC · ${r.accounts.length} account(s) · ${r.localFiles} wrangler file(s) · read-only. ` +
      `**${counts.length ? counts.join(', ') : 'no findings'}**.`,
    '',
  ];
  if (r.findings.length) {
    lines.push('| Severity | Check | Account | Resource | Finding | Fix |', '|---|---|---|---|---|---|');
    for (const f of r.findings.slice(0, MAX_SUMMARY_ROWS)) {
      lines.push(`| ${f.severity} | ${mdCell(CHECK_NAMES[f.check] ?? f.check)} | ${mdCell(f.account)} | ${mdCell(f.resource)} | ${mdCell(f.title)} | ${mdCell(f.fix)} |`);
    }
    if (r.findings.length > MAX_SUMMARY_ROWS) lines.push('', `${r.findings.length - MAX_SUMMARY_ROWS} more not shown; run the CLI with --html for all of them.`);
    lines.push('');
  }
  if (r.gaps.length) {
    lines.push(`<details><summary>Not checked (${r.gaps.length})</summary>`, '', ...r.gaps.map((g) => `- ${mdCell(g.account)}: ${mdCell(g.what)} (${mdCell(g.reason)})`), '', '</details>', '');
  }
  return lines.join('\n') + '\n';
}
