// Terminal table. Colour only when asked (the CLI passes isTTY && !NO_COLOR).

import { BRAND } from '../brand.js';
import type { AuditResult, Finding, Severity } from '../types.js';

const COLORS: Record<Severity, string> = { critical: '\x1b[1;37;41m', high: '\x1b[31m', medium: '\x1b[33m', low: '\x1b[36m', info: '\x1b[2m' };
const RESET = '\x1b[0m';
const DIM = '\x1b[2m';

function cut(s: string, w: number): string {
  return s.length <= w ? s.padEnd(w) : `${s.slice(0, w - 1)}…`;
}

export function renderText(r: AuditResult, opts: { color?: boolean; width?: number; minSeverity?: Severity } = {}): string {
  const color = opts.color ?? false;
  const width = Math.max(80, opts.width ?? 120);
  const c = (code: string, s: string) => (color ? `${code}${s}${RESET}` : s);
  const lines: string[] = [];
  const acc = r.accounts.map((a) => `${a.name} (${a.scripts} scripts, ${a.zones} zones)`).join(', ') || 'none';
  lines.push(`${BRAND.fullName} — ${r.generatedAt.slice(0, 16).replace('T', ' ')} UTC`);
  lines.push(`Accounts: ${acc}. Local wrangler files: ${r.localFiles}.`);
  lines.push('');

  const findings: Finding[] = r.findings;
  if (findings.length === 0) lines.push('No findings.');
  else {
    const wSev = 8, wCheck = 26, wAcct = 14;
    const rest = width - wSev - wCheck - wAcct - 8;
    const wRes = Math.max(18, Math.floor(rest * 0.38));
    const wTitle = rest - wRes;
    lines.push(c(DIM, [cut('SEVERITY', wSev), cut('CHECK', wCheck), cut('ACCOUNT', wAcct), cut('RESOURCE', wRes), 'FINDING'].join('  ')));
    for (const f of findings) {
      lines.push([c(COLORS[f.severity], cut(f.severity.toUpperCase(), wSev)), cut(f.check, wCheck), cut(f.account, wAcct), cut(f.resource, wRes), cut(f.title, wTitle).trimEnd()].join('  '));
      lines.push(c(DIM, `${' '.repeat(wSev + 2)}fix: ${f.fix}`));
    }
  }
  lines.push('');
  lines.push(
    'Summary: ' +
      (Object.entries(r.summary) as [Severity, number][])
        .filter(([, n]) => n > 0)
        .map(([s, n]) => c(COLORS[s], `${n} ${s}`))
        .join(', ') || 'Summary: clean',
  );
  if (r.gaps.length) {
    lines.push('');
    lines.push(`Not checked (${r.gaps.length}):`);
    for (const g of r.gaps) lines.push(`  ${g.account}: ${g.what} — ${g.reason}`);
  }
  return lines.join('\n') + '\n';
}
