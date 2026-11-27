import { describe, expect, it } from 'vitest';
import { collectSnapshot } from '../src/core/audit.js';
import { ACCOUNT_ID, fakeCloudflare, NOW, SECRET_VALUE } from './fixtures/cloudflare.js';

describe('collect', () => {
  it('reads every part of the account into the snapshot', async () => {
    const f = fakeCloudflare();
    const { snapshot } = await collectSnapshot({ tokens: ['test-token'], fetch: f.fetch, now: NOW });
    const a = snapshot.accounts[0]!;
    expect(a.id).toBe(ACCOUNT_ID);
    expect(a.workersSubdomain).toBe('acme-sub');
    expect(a.scripts?.map((s) => s.name)).toContain('shop');
    const shop = a.scripts!.find((s) => s.name === 'shop')!;
    expect(shop.subdomain).toEqual({ enabled: true, previewsEnabled: true });
    expect(shop.bindings?.find((b) => b.type === 'ratelimit')?.namespaceId).toBe('1001');
    expect(shop.secretNames).toEqual(['API_KEY', 'STRIPE_KEY']);
    expect(shop.lastDeployedOn).toBe('2026-10-20T10:00:00Z');
    expect(a.zones?.find((z) => z.name === 'example.com')?.settings).toEqual({
      minTlsVersion: '1.0',
      alwaysUseHttps: 'off',
      hsts: { enabled: false, maxAge: 0, includeSubdomains: false },
    });
    expect(a.accessApps?.map((x) => x.domains).flat()).toEqual(['admin.example.com', 'internal.example.com/admin']);
    expect(a.tokens?.map((t) => `${t.scope}:${t.name}`)).toEqual(['account:ci-deploy', 'account:readonly-audit', 'account:disabled-one', 'user:old-laptop']);
    expect(a.gaps).toEqual([]);
  });

  it('never keeps a secret value anywhere in the snapshot', async () => {
    const { snapshot } = await collectSnapshot({ tokens: ['test-token'], fetch: fakeCloudflare().fetch, now: NOW });
    expect(JSON.stringify(snapshot)).not.toContain(SECRET_VALUE);
  });

  it('uses GET only and asks for cron schedules only for scheduled scripts', async () => {
    const f = fakeCloudflare();
    await collectSnapshot({ tokens: ['test-token'], fetch: f.fetch, now: NOW });
    expect(new Set(f.calls.map((c) => c.method))).toEqual(new Set(['GET']));
    const sched = f.calls.filter((c) => c.url.endsWith('/schedules')).map((c) => c.url);
    expect(sched).toEqual([`/client/v4/accounts/${ACCOUNT_ID}/workers/scripts/old-cron/schedules`]);
  });

  it('turns a missing scope into a coverage gap instead of failing', async () => {
    const f = fakeCloudflare({ deny: [`/accounts/${ACCOUNT_ID}/access/apps`, '/user/tokens', `/accounts/${ACCOUNT_ID}/workers/scripts/shop/secrets`] });
    const { snapshot } = await collectSnapshot({ tokens: ['test-token'], fetch: f.fetch, now: NOW });
    const a = snapshot.accounts[0]!;
    expect(a.accessApps).toBeUndefined();
    expect(a.gaps.map((g) => g.what).sort()).toEqual(['Access applications', 'per-script secret names', 'user API tokens']);
    expect(a.gaps[0]!.reason).toMatch(/lacks the scope/);
    expect(a.scripts).toHaveLength(7);
  });

  it('merges tokens that see the same account and records a bad token as a gap', async () => {
    const f = fakeCloudflare();
    const { snapshot } = await collectSnapshot({ tokens: ['test-token', 'second-token', 'bad-token'], fetch: f.fetch, now: NOW });
    expect(snapshot.accounts).toHaveLength(1);
    expect(snapshot.localGaps).toEqual([{ account: 'token #3', what: 'account list', reason: expect.stringMatching(/lacks the scope \(HTTP 401\)/) }]);
  });

  it('shallow mode skips the per-script calls', async () => {
    const f = fakeCloudflare();
    await collectSnapshot({ tokens: ['test-token'], fetch: f.fetch, now: NOW, collect: { shallow: true } });
    expect(f.calls.some((c) => c.url.includes('/workers/scripts/'))).toBe(false);
  });
});
