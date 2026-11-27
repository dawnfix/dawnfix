import { describe, expect, it } from 'vitest';
import { CfApiError, CfClient } from '../src/core/client.js';
import { fakeCloudflare } from './fixtures/cloudflare.js';

describe('CfClient', () => {
  it('refuses anything but GET before a request leaves', async () => {
    const f = fakeCloudflare();
    const c = new CfClient({ token: 'test-token', fetch: f.fetch });
    for (const m of ['POST', 'PUT', 'PATCH', 'DELETE']) await expect(c.request(m, '/accounts')).rejects.toThrow(/read-only/);
    expect(f.calls).toHaveLength(0);
  });

  it('sends the bearer token to api.cloudflare.com/client/v4 only', async () => {
    const f = fakeCloudflare();
    const c = new CfClient({ token: 'test-token', fetch: f.fetch });
    await c.get('/accounts');
    expect(f.calls[0]).toEqual({ method: 'GET', url: '/client/v4/accounts', auth: 'Bearer test-token' });
  });

  it('follows result_info pages', async () => {
    const page = (n: number) => ({ success: true, result: [{ id: `z${n}` }], result_info: { page: n, total_pages: 3 } });
    const seen: string[] = [];
    const c = new CfClient({
      token: 't',
      fetch: async (url) => {
        seen.push(url);
        const n = Number(new URL(url).searchParams.get('page'));
        return { status: 200, headers: { get: () => null }, json: async () => page(n) };
      },
    });
    const all = await c.getAll<{ id: string }>('/zones', { 'account.id': 'a' }, 50);
    expect(all.map((z) => z.id)).toEqual(['z1', 'z2', 'z3']);
    expect(seen[0]).toContain('account.id=a&page=1&per_page=50');
  });

  it('waits out a 429 using retry-after, then succeeds', async () => {
    const f = fakeCloudflare({ throttleOnce: ['/accounts'] });
    const slept: number[] = [];
    const c = new CfClient({ token: 'test-token', fetch: f.fetch, sleep: async (ms) => void slept.push(ms) });
    const env = await c.get<unknown[]>('/accounts');
    expect(env.result).toHaveLength(1);
    expect(slept).toEqual([1000]);
  });

  it('raises a permission error for 403', async () => {
    const f = fakeCloudflare({ deny: ['/user/tokens'] });
    const c = new CfClient({ token: 'test-token', fetch: f.fetch });
    const err = await c.get('/user/tokens').catch((e) => e);
    expect(err).toBeInstanceOf(CfApiError);
    expect((err as CfApiError).isPermission).toBe(true);
  });

  it('never runs more requests at once than the concurrency limit', async () => {
    let active = 0;
    let peak = 0;
    const c = new CfClient({
      token: 't',
      concurrency: 2,
      fetch: async () => {
        active++;
        peak = Math.max(peak, active);
        await new Promise((r) => setTimeout(r, 5));
        active--;
        return { status: 200, headers: { get: () => null }, json: async () => ({ success: true, result: [] }) };
      },
    });
    await Promise.all(Array.from({ length: 8 }, (_, i) => c.get(`/x/${i}`)));
    expect(peak).toBe(2);
  });
});
