// A recorded-style Cloudflare account, shaped like the documented v4 responses, served by
// a fake fetch. Every check has at least one planted problem here and at least one clean
// case next to it. Names are generic on purpose.

import type { FetchLike } from '../../src/core/client.js';

export const ACCOUNT_ID = '0123456789abcdef0123456789abcdef';
export const ZONE_COM = 'aaaa0000aaaa0000aaaa0000aaaa0000';
export const ZONE_ORG = 'bbbb0000bbbb0000bbbb0000bbbb0000';
export const SECRET_VALUE = 'sk_live_SHOULD_NEVER_APPEAR';

const ok = (result: unknown, result_info?: unknown) => ({ success: true, errors: [], messages: [], result, ...(result_info ? { result_info } : {}) });
const denied = { success: false, errors: [{ code: 10000, message: 'Authentication error' }], messages: [], result: null };

type Script = { id: string; handlers: string[]; compatibility_date: string; modified_on: string; created_on: string };
const script = (id: string, handlers: string[], compatibility_date: string, modified_on: string): Script => ({ id, handlers, compatibility_date, modified_on, created_on: '2024-01-01T00:00:00Z' });

export const SCRIPTS: Script[] = [
  script('shop', ['fetch'], '2026-09-01', '2026-10-20T10:00:00Z'),
  script('blog', ['fetch'], '2023-01-01', '2026-10-01T10:00:00Z'),
  script('admin', ['fetch'], '2026-06-01', '2026-10-01T10:00:00Z'),
  script('internal', ['fetch'], '2026-06-01', '2026-10-01T10:00:00Z'),
  script('old-cron', ['scheduled'], '2025-06-01', '2025-01-01T10:00:00Z'),
  script('queue-consumer', ['queue'], '2026-06-01', '2026-10-01T10:00:00Z'),
  script('api', ['fetch'], '2026-06-01', '2026-10-01T10:00:00Z'),
];

const subdomain: Record<string, { enabled: boolean; previews_enabled: boolean }> = {
  shop: { enabled: true, previews_enabled: true },
  'old-cron': { enabled: false, previews_enabled: false },
};

const ratelimit = (name: string, namespace_id: string) => ({ type: 'ratelimit', name, namespace_id, simple: { limit: 100, period: 60 } });
const bindings: Record<string, unknown[]> = {
  shop: [ratelimit('PAGE_LIMIT', '1001'), { type: 'service', name: 'API', service: 'api' }, { type: 'secret_text', name: 'API_KEY' }],
  blog: [ratelimit('PAGE_LIMIT', '1001')],
  admin: [ratelimit('PAGE_LIMIT', '1101'), ratelimit('FORM_LIMIT', '1101')],
};

const secrets: Record<string, unknown[]> = {
  shop: [
    { name: 'API_KEY', type: 'secret_text', text: SECRET_VALUE },
    { name: 'STRIPE_KEY', type: 'secret_text', text: SECRET_VALUE },
  ],
};

const deployments: Record<string, string> = {
  shop: '2026-10-20T10:00:00Z',
  'old-cron': '2025-01-01T10:00:00Z',
};

const dns = (name: string, type: string, content: string, proxied = true) => ({ id: `${type}-${name}`, name, type, content, proxied, ttl: 1 });

export const ROUTES: Record<string, unknown[]> = {
  [ZONE_COM]: [
    { id: 'r1', pattern: 'blog.example.com/*', script: 'blog' },
    { id: 'r2', pattern: 'internal.example.com/*', script: 'internal' },
    { id: 'r3', pattern: 'legacy.example.com/*', script: 'ghost' },
    { id: 'r4', pattern: 'blog.example.com/static/*' },
  ],
  [ZONE_ORG]: [],
};

export const DNS: Record<string, unknown[]> = {
  [ZONE_COM]: [
    dns('example.com', 'A', '203.0.113.10'),
    dns('www.example.com', 'CNAME', 'example.com'),
    dns('shop.example.com', 'AAAA', '100::'),
    dns('blog.example.com', 'AAAA', '100::'),
    dns('internal.example.com', 'AAAA', '100::'),
    dns('legacy.example.com', 'AAAA', '100::'),
    dns('stale.example.com', 'A', '192.0.2.1'),
    dns('docs.example.com', 'CNAME', 'docs-old.example.com'),
    dns('status.example.com', 'CNAME', 'gone.acme-sub.workers.dev'),
    dns('edge.example.com', 'CNAME', 'shop.other-sub.workers.dev'),
    dns('cdn.example.com', 'CNAME', 'assets.example.org'),
    dns('mail.example.com', 'MX', 'mx.example.net', false),
  ],
  [ZONE_ORG]: [dns('example.org', 'A', '203.0.113.20'), dns('*.example.org', 'A', '203.0.113.20')],
};

const settings: Record<string, Record<string, unknown>> = {
  [ZONE_COM]: {
    min_tls_version: '1.0',
    always_use_https: 'off',
    security_header: { strict_transport_security: { enabled: false, max_age: 0, include_subdomains: false, preload: false, nosniff: false } },
  },
  [ZONE_ORG]: {
    min_tls_version: '1.2',
    always_use_https: 'on',
    security_header: { strict_transport_security: { enabled: true, max_age: 31536000, include_subdomains: true, preload: false, nosniff: true } },
  },
};

export const ACCESS_APPS = [
  { id: 'app1', name: 'Admin', type: 'self_hosted', domain: 'admin.example.com' },
  { id: 'app2', name: 'Internal admin path', type: 'self_hosted', domain: 'internal.example.com/admin', destinations: [{ type: 'public', uri: 'internal.example.com/admin' }] },
];

const pg = (name: string) => ({ id: name.toLowerCase().replace(/\W+/g, '-'), name });
export const ACCOUNT_TOKENS = [
  {
    id: 'tok-ci',
    name: 'ci-deploy',
    status: 'active',
    issued_on: '2025-03-01T00:00:00Z',
    last_used_on: '2026-10-25T00:00:00Z',
    policies: [{ id: 'p1', effect: 'allow', permission_groups: [pg('Workers Scripts Write'), pg('Zone Read')], resources: { 'com.cloudflare.api.account.*': '*' } }],
  },
  {
    id: 'tok-audit',
    name: 'readonly-audit',
    status: 'active',
    issued_on: '2026-10-01T00:00:00Z',
    expires_on: '2027-04-01T00:00:00Z',
    last_used_on: '2026-10-26T00:00:00Z',
    condition: { request_ip: { in: ['198.51.100.0/24'], not_in: [] } },
    policies: [{ id: 'p2', effect: 'allow', permission_groups: [pg('Workers Scripts Read'), pg('Zone Read')], resources: { [`com.cloudflare.api.account.${ACCOUNT_ID}`]: '*' } }],
  },
  { id: 'tok-off', name: 'disabled-one', status: 'disabled', policies: [] },
];

export const USER_TOKENS = [
  {
    id: 'tok-laptop',
    name: 'old-laptop',
    status: 'active',
    issued_on: '2025-01-01T00:00:00Z',
    expires_on: '2027-01-01T00:00:00Z',
    last_used_on: '2025-12-01T00:00:00Z',
    policies: [{ id: 'p3', effect: 'allow', permission_groups: [pg('DNS Read')], resources: { [`com.cloudflare.api.account.zone.${ZONE_COM}`]: '*' } }],
  },
];

export interface FakeOptions {
  /** Paths (prefix match, without query) that answer 403. */
  deny?: string[];
  /** Responses that override the defaults, by exact path. */
  override?: Record<string, unknown>;
  /** Paths that 429 once before answering. */
  throttleOnce?: string[];
}

export interface Fake {
  fetch: FetchLike;
  calls: { method: string; url: string; auth: string | undefined }[];
}

export function fakeCloudflare(opts: FakeOptions = {}): Fake {
  const calls: Fake['calls'] = [];
  const throttled = new Set<string>();
  const routes: Record<string, unknown> = {
    '/accounts': ok([{ id: ACCOUNT_ID, name: 'Example Co' }], { page: 1, per_page: 50, total_pages: 1, count: 1, total_count: 1 }),
    [`/accounts/${ACCOUNT_ID}`]: ok({ id: ACCOUNT_ID, name: 'Example Co' }),
    [`/accounts/${ACCOUNT_ID}/workers/subdomain`]: ok({ subdomain: 'acme-sub' }),
    [`/accounts/${ACCOUNT_ID}/workers/scripts`]: ok(SCRIPTS.map((s) => ({ ...s, routes: [] }))),
    [`/accounts/${ACCOUNT_ID}/workers/domains`]: ok([
      { id: 'd1', hostname: 'shop.example.com', service: 'shop', zone_id: ZONE_COM, zone_name: 'example.com', enabled: true },
      { id: 'd2', hostname: 'admin.example.com', service: 'admin', zone_id: ZONE_COM, zone_name: 'example.com', enabled: true },
      { id: 'd3', hostname: 'old.example.com', service: 'removed-worker', zone_id: ZONE_COM, zone_name: 'example.com', enabled: true },
    ]),
    '/zones': ok(
      [
        { id: ZONE_COM, name: 'example.com', status: 'active' },
        { id: ZONE_ORG, name: 'example.org', status: 'active' },
      ],
      { page: 1, per_page: 50, total_pages: 1, count: 2, total_count: 2 },
    ),
    [`/accounts/${ACCOUNT_ID}/access/apps`]: ok(ACCESS_APPS, { page: 1, per_page: 1000, total_pages: 1, count: 2, total_count: 2 }),
    [`/accounts/${ACCOUNT_ID}/tokens`]: ok(ACCOUNT_TOKENS, { page: 1, per_page: 50, total_pages: 1, count: 3, total_count: 3 }),
    '/user/tokens': ok(USER_TOKENS, { page: 1, per_page: 50, total_pages: 1, count: 1, total_count: 1 }),
  };
  for (const s of SCRIPTS) {
    const b = `/accounts/${ACCOUNT_ID}/workers/scripts/${s.id}`;
    routes[`${b}/subdomain`] = ok(subdomain[s.id] ?? { enabled: false, previews_enabled: false });
    routes[`${b}/settings`] = ok({ bindings: bindings[s.id] ?? [], compatibility_date: s.compatibility_date, usage_model: 'standard' });
    routes[`${b}/secrets`] = ok(secrets[s.id] ?? []);
    routes[`${b}/deployments`] = ok({
      deployments: [{ id: '11111111-1111-1111-1111-111111111111', created_on: deployments[s.id] ?? s.modified_on, source: 'wrangler', strategy: 'percentage', versions: [{ version_id: '22222222-2222-2222-2222-222222222222', percentage: 100 }] }],
    });
    routes[`${b}/schedules`] = ok({ schedules: [] });
  }
  for (const z of [ZONE_COM, ZONE_ORG]) {
    routes[`/zones/${z}/workers/routes`] = ok(ROUTES[z]);
    routes[`/zones/${z}/dns_records`] = ok(DNS[z], { page: 1, per_page: 1000, total_pages: 1, count: DNS[z]!.length, total_count: DNS[z]!.length });
    for (const [k, v] of Object.entries(settings[z]!)) routes[`/zones/${z}/settings/${k}`] = ok({ id: k, value: v, editable: true, modified_on: null });
  }
  Object.assign(routes, opts.override ?? {});

  const fetch: FetchLike = async (input, init) => {
    const url = new URL(input);
    calls.push({ method: init?.method ?? 'GET', url: url.pathname + url.search, auth: init?.headers?.authorization });
    const path = url.pathname.replace(/^\/client\/v4/, '');
    const respond = (status: number, body: unknown, headers: Record<string, string> = {}) => ({
      status,
      headers: { get: (n: string) => headers[n.toLowerCase()] ?? null },
      json: async () => body,
    });
    if (url.origin !== 'https://api.cloudflare.com') return respond(400, { success: false, errors: [{ code: 1, message: 'wrong host' }] });
    if (init?.headers?.authorization !== 'Bearer test-token' && init?.headers?.authorization !== 'Bearer second-token') return respond(401, denied);
    if (opts.throttleOnce?.includes(path) && !throttled.has(path)) {
      throttled.add(path);
      return respond(429, { success: false, errors: [{ code: 971, message: 'Please wait' }] }, { 'retry-after': '1' });
    }
    if (opts.deny?.some((d) => path.startsWith(d))) return respond(403, denied);
    const body = routes[path];
    if (body === undefined) return respond(404, { success: false, errors: [{ code: 7003, message: `No route for ${path}` }], messages: [], result: null });
    return respond(200, body);
  };
  return { fetch, calls };
}

export const NOW = new Date('2026-10-27T12:00:00Z');
