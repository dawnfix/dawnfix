// Hostname helpers shared by the checks.

/** "https://a.example.com/x/*" -> "a.example.com". Route patterns have no scheme, but tolerate one. */
export function hostOf(pattern: string): string {
  return pattern.replace(/^[a-z]+:\/\//i, '').split('/')[0]!.toLowerCase().replace(/\.$/, '');
}

export function pathOf(pattern: string): string {
  const p = pattern.replace(/^[a-z]+:\/\//i, '');
  const at = p.indexOf('/');
  return at < 0 ? '' : p.slice(at);
}

/** Does `rule` (exact or "*.example.com" or "*example.com") match `host`? */
export function hostMatches(rule: string, host: string): boolean {
  const r = rule.toLowerCase();
  const h = host.toLowerCase();
  if (r === h || r === '*') return true;
  if (r.startsWith('*.')) return h.endsWith(r.slice(1)) && h.length > r.length - 1;
  if (r.startsWith('*')) return h.endsWith(r.slice(1));
  return false;
}

/** Whether an Access domain covers the host fully, only on some paths, or not at all. */
export function accessCoverage(accessDomain: string, host: string): 'full' | 'partial' | 'none' {
  if (!hostMatches(hostOf(accessDomain), host)) return 'none';
  const path = pathOf(accessDomain);
  return path === '' || path === '/' || path === '/*' ? 'full' : 'partial';
}

export function monthsBetween(from: Date, to: Date): number {
  return (to.getUTCFullYear() - from.getUTCFullYear()) * 12 + (to.getUTCMonth() - from.getUTCMonth()) - (to.getUTCDate() < from.getUTCDate() ? 1 : 0);
}

export function daysBetween(from: Date, to: Date): number {
  return Math.floor((to.getTime() - from.getTime()) / 86_400_000);
}
