import { describe, expect, it } from 'vitest';
import { scanRepos } from '../src/node/scan.js';
import { REPOS } from './helpers.js';

describe('scanRepos', () => {
  it('finds jsonc and toml configs (including apps/*), skips node_modules, reports unparsable files', async () => {
    const r = await scanRepos([`${REPOS}/*`], { base: REPOS });
    expect(r.files.sort()).toEqual(['~/blog/wrangler.toml', '~/broken/wrangler.toml', '~/shop/wrangler.jsonc', '~/tools/apps/portal/wrangler.jsonc']);
    expect(r.workers.map((w) => w.name).sort()).toEqual(['blog', 'blog-staging', 'portal', 'shop']);
    expect(r.gaps).toEqual([{ account: 'local', what: '~/broken/wrangler.toml', reason: expect.stringMatching(/could not parse: TOML line 2/) }]);
  });
  it('records auth markers from the Worker source', async () => {
    const r = await scanRepos([`${REPOS}/tools`], { base: REPOS });
    expect(r.workers[0]!.authMarkers.sort()).toEqual(['passkey / WebAuthn', 'sign-in route']);
  });
  it('uses custom markers from config', async () => {
    const r = await scanRepos([`${REPOS}/shop`], { base: REPOS, markers: [{ label: 'custom', pattern: 'new Response\\("shop"' }] });
    expect(r.workers[0]!.authMarkers).toEqual(['custom']);
  });
  it('says so when a directory holds no wrangler file', async () => {
    const r = await scanRepos([`${REPOS}/shop/src`], { base: REPOS });
    expect(r.gaps[0]!.reason).toMatch(/no wrangler/);
  });
});
