import { describe, expect, it } from 'vitest';
import { renderHtml } from '../src/core/report/html.js';
import { renderText } from '../src/core/report/text.js';
import type { AuditResult } from '../src/core/types.js';
import { apiSnapshot, run } from './helpers.js';

const evil: AuditResult = {
  generatedAt: '2026-10-27T12:00:00.000Z',
  findings: [{ check: 'dangling-dns', severity: 'high', account: '<b>acct</b>', resource: '"><script>alert(1)</script>', title: 't & t', detail: "it's", fix: 'f', source: 'api' }],
  gaps: [{ account: 'a', what: '<img src=x>', reason: 'r' }],
  summary: { critical: 0, high: 1, medium: 0, low: 0, info: 0 },
  accounts: [{ id: 'x', name: 'A<', scripts: 1, zones: 0 }],
  localFiles: 0,
};

describe('HTML report', () => {
  it('escapes every value', () => {
    const h = renderHtml(evil);
    expect(h).not.toContain('<script>alert');
    expect(h).not.toContain('<img src=x>');
    expect(h).toContain('&quot;&gt;&lt;script&gt;');
    expect(h).toContain('t &amp; t');
  });
  it('is self-contained, themed for light and dark, and sized for phones', async () => {
    const h = renderHtml(run(await apiSnapshot()).result);
    expect(h).not.toMatch(/<link\b|<script[^>]+src=|<img\b|@import|url\(/i);
    expect(h).not.toMatch(/https?:\/\//);
    expect(h).toContain('prefers-color-scheme:dark');
    expect(h).toContain('name="viewport"');
    expect(h).toContain('@media (max-width:560px)');
    expect(h.match(/class="f"/g)).toHaveLength(run(await apiSnapshot()).result.findings.length);
  });
});

describe('text report', () => {
  it('prints a row and a fix line per finding, the summary and the gaps, without colour by default', async () => {
    const s = await apiSnapshot({ deny: ['/user/tokens'] });
    const t = renderText(run(s).result, { width: 120 });
    expect(t).not.toContain('\x1b[');
    expect(t).toMatch(/^HIGH\s+workers-dev-enabled\s+Example Co\s+shop\s+Reachable on workers.dev/m);
    expect(t).toMatch(/fix: Set "workers_dev": false/);
    expect(t).toMatch(/Summary: \d+ high, \d+ medium, \d+ low/);
    expect(t).toContain('Not checked (1):');
    expect(t.split('\n').every((l) => l.length <= 120 || l.includes('fix:'))).toBe(true);
  });
  it('colours severities when asked', async () => {
    expect(renderText(run(await apiSnapshot()).result, { color: true })).toContain('\x1b[31mHIGH');
  });
});
