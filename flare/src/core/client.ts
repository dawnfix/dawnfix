// The only code that talks to Cloudflare. GET only: a method other than GET is refused here,
// before anything leaves the process, so the audit cannot change an account even if a
// token with write scopes is handed to it. fetch is injected so tests replay recorded
// responses and a Worker passes its own.

import { BRAND, CLOUDFLARE_API } from './brand.js';

export type FetchLike = (input: string, init?: { method?: string; headers?: Record<string, string> }) => Promise<{
  status: number;
  headers: { get(name: string): string | null };
  json(): Promise<unknown>;
}>;

export class CfApiError extends Error {
  constructor(
    readonly path: string,
    readonly status: number,
    readonly codes: number[],
    message: string,
  ) {
    super(message);
  }
  /** 403, or 401/400 with the "not authorized" family of codes: the token lacks a scope. */
  get isPermission(): boolean {
    return this.status === 403 || this.status === 401 || this.codes.includes(10000) || this.codes.includes(9109);
  }
}

interface Envelope<T> {
  success: boolean;
  errors?: { code: number; message: string }[];
  result: T;
  result_info?: { page?: number; per_page?: number; total_pages?: number; total_count?: number; count?: number };
}

export interface ClientOptions {
  token: string;
  fetch: FetchLike;
  baseUrl?: string;
  /** Concurrent requests. Cloudflare allows 1200 per 5 minutes per user; 4 stays far below. */
  concurrency?: number;
  maxRetries?: number;
  sleep?: (ms: number) => Promise<void>;
}

export class CfClient {
  private active = 0;
  private queue: (() => void)[] = [];
  readonly calls: string[] = [];

  constructor(private readonly opts: ClientOptions) {}

  private async slot<T>(fn: () => Promise<T>): Promise<T> {
    const limit = this.opts.concurrency ?? 4;
    if (this.active >= limit) await new Promise<void>((r) => this.queue.push(r));
    this.active++;
    try {
      return await fn();
    } finally {
      this.active--;
      this.queue.shift()?.();
    }
  }

  async get<T>(path: string, query: Record<string, string | number> = {}): Promise<Envelope<T>> {
    return this.request<T>('GET', path, query);
  }

  async request<T>(method: string, path: string, query: Record<string, string | number> = {}): Promise<Envelope<T>> {
    if (method !== 'GET') throw new Error(`${BRAND.cli} is read-only: refused ${method} ${path}`);
    const qs = new URLSearchParams(Object.entries(query).map(([k, v]) => [k, String(v)])).toString();
    // Only an explicitly passed baseUrl counts (tests); never one inherited from a prototype.
    const base = Object.hasOwn(this.opts, 'baseUrl') && this.opts.baseUrl ? this.opts.baseUrl : CLOUDFLARE_API;
    const url = `${base}${path}${qs ? `?${qs}` : ''}`;
    const sleep = this.opts.sleep ?? ((ms: number) => new Promise((r) => setTimeout(r, ms)));
    return this.slot(async () => {
      for (let attempt = 0; ; attempt++) {
        this.calls.push(`GET ${path}${qs ? `?${qs}` : ''}`);
        const res = await this.opts.fetch(url, {
          method: 'GET',
          headers: { authorization: `Bearer ${this.opts.token}`, 'user-agent': BRAND.userAgent, accept: 'application/json' },
        });
        if ((res.status === 429 || res.status >= 500) && attempt < (this.opts.maxRetries ?? 3)) {
          const after = Number(res.headers.get('retry-after'));
          await sleep(Number.isFinite(after) && after > 0 ? Math.min(after, 60) * 1000 : 500 * 2 ** attempt);
          continue;
        }
        let body: Envelope<T> | undefined;
        try {
          body = (await res.json()) as Envelope<T>;
        } catch {
          body = undefined;
        }
        if (res.status >= 400 || !body || body.success === false) {
          const errs = body?.errors ?? [];
          throw new CfApiError(
            path,
            res.status,
            errs.map((e) => e.code),
            errs.map((e) => `${e.code}: ${e.message}`).join('; ') || `HTTP ${res.status}`,
          );
        }
        return body;
      }
    });
  }

  /** Follows result_info.total_pages. Endpoints without result_info return their one page. */
  async getAll<T>(path: string, query: Record<string, string | number> = {}, perPage = 100): Promise<T[]> {
    const out: T[] = [];
    for (let page = 1; page <= 1000; page++) {
      const env = await this.get<T[]>(path, { ...query, page, per_page: perPage });
      const items = Array.isArray(env.result) ? env.result : [];
      out.push(...items);
      const total = env.result_info?.total_pages;
      if (!total || page >= total || items.length === 0) break;
    }
    return out;
  }
}
