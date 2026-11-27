// Sketch, not deployed: the same audit on a Worker cron. Only src/core is imported, and
// `npm run typecheck` compiles this file with no Node types to keep it that way.
// The secret-name baseline moves from ~/.flare/state.json to one KV key; local repo
// scanning has no place here (a CI job could upload wrangler files instead).

import { audit, collectSnapshot, renderHtml, DEFAULT_OPTIONS, type FetchLike } from '../src/core/index.js';

interface Kv {
  get(key: string): Promise<string | null>;
  put(key: string, value: string): Promise<void>;
}
interface Env {
  /** Comma-separated read-only tokens, stored as a Worker secret. */
  CF_API_TOKENS: string;
  STATE: Kv;
  PUBLIC_HOSTNAMES?: string;
}

export default {
  async scheduled(_event: unknown, env: Env): Promise<void> {
    const now = new Date();
    const { snapshot } = await collectSnapshot({
      tokens: env.CF_API_TOKENS.split(',').map((t) => t.trim()).filter(Boolean),
      fetch: fetch as unknown as FetchLike,
      now,
      concurrency: 4, // a Worker invocation allows 6 simultaneous outbound connections
    });
    const prev = await env.STATE.get('secrets-baseline');
    const { result, secretsBaseline } = audit(snapshot, {
      ...DEFAULT_OPTIONS,
      publicHostnames: (env.PUBLIC_HOSTNAMES ?? '').split(',').filter(Boolean),
      ...(prev ? { secretsBaseline: JSON.parse(prev) as Record<string, string[]> } : {}),
      now,
    });
    await env.STATE.put('secrets-baseline', JSON.stringify(secretsBaseline));
    await env.STATE.put('latest.json', JSON.stringify(result));
    await env.STATE.put('latest.html', renderHtml(result));
  },
};
