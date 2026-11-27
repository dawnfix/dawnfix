// Parses wrangler.jsonc / wrangler.json / wrangler.toml into LocalWorker records. Pure (no
// fs), so a Worker could audit configs it was sent. The TOML reader covers what wrangler
// files use: tables, arrays of tables, dotted keys, inline tables, arrays, strings,
// numbers, booleans and dates. It is not a general TOML implementation.

import type { LocalWorker } from './types.js';

/* eslint-disable @typescript-eslint/no-explicit-any */
type Obj = Record<string, any>;

// ---- JSONC ------------------------------------------------------------------------------

export function parseJsonc(text: string): Obj {
  let out = '';
  let i = 0;
  while (i < text.length) {
    const c = text[i]!;
    if (c === '"') {
      const start = i++;
      while (i < text.length && text[i] !== '"') i += text[i] === '\\' ? 2 : 1;
      out += text.slice(start, ++i);
    } else if (c === '/' && text[i + 1] === '/') {
      while (i < text.length && text[i] !== '\n') i++;
    } else if (c === '/' && text[i + 1] === '*') {
      i = text.indexOf('*/', i + 2);
      i = i < 0 ? text.length : i + 2;
    } else {
      out += c;
      i++;
    }
  }
  // Trailing commas: wrangler accepts them, JSON.parse does not.
  return JSON.parse(out.replace(/,(\s*[}\]])/g, '$1')) as Obj;
}

// ---- TOML (the subset wrangler files use) -----------------------------------------------

// Keys that would reach Object.prototype. Wrangler files come from repos we scan, so
// they are untrusted: refuse these outright and build every table without a prototype.
const FORBIDDEN_KEYS = new Set(['__proto__', 'constructor', 'prototype']);
const table = (): Obj => Object.create(null) as Obj;

export function parseToml(text: string): Obj {
  const root: Obj = table();
  let current: Obj = root;
  let i = 0;
  const n = text.length;

  const ws = () => {
    while (i < n && (text[i] === ' ' || text[i] === '\t')) i++;
  };
  const wsNl = () => {
    for (;;) {
      while (i < n && /\s/.test(text[i]!)) i++;
      if (text[i] === '#') while (i < n && text[i] !== '\n') i++;
      else break;
    }
  };
  const fail = (msg: string): never => {
    const line = text.slice(0, i).split('\n').length;
    throw new Error(`TOML line ${line}: ${msg}`);
  };

  const parseString = (): string => {
    const q = text[i]!;
    const triple = text.startsWith(q.repeat(3), i);
    if (triple) {
      i += 3;
      if (text[i] === '\n') i++;
      const end = text.indexOf(q.repeat(3), i);
      if (end < 0) fail('unterminated multi-line string');
      const s = text.slice(i, end);
      i = end + 3;
      return q === '"' ? unescape(s) : s;
    }
    i++;
    let s = '';
    while (i < n && text[i] !== q) {
      if (text[i] === '\n') fail('newline in string');
      if (q === '"' && text[i] === '\\') {
        s += text.slice(i, i + 2);
        i += 2;
      } else s += text[i++];
    }
    if (text[i] !== q) fail('unterminated string');
    i++;
    return q === '"' ? unescape(s) : s;
  };
  const unescape = (s: string) =>
    s.replace(/\\(u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|.)/g, (_, e: string) => {
      if (e[0] === 'u' || e[0] === 'U') return String.fromCodePoint(parseInt(e.slice(1), 16));
      return ({ n: '\n', t: '\t', r: '\r', '"': '"', '\\': '\\', b: '\b', f: '\f' } as Record<string, string>)[e] ?? e;
    });

  const parseKey = (): string[] => {
    const parts: string[] = [];
    for (;;) {
      ws();
      if (text[i] === '"' || text[i] === "'") parts.push(parseString());
      else {
        const m = /^[A-Za-z0-9_-]+/.exec(text.slice(i));
        if (!m) fail('expected a key');
        parts.push(m![0]);
        i += m![0].length;
      }
      if (FORBIDDEN_KEYS.has(parts[parts.length - 1]!)) fail(`forbidden key "${parts[parts.length - 1]}"`);
      ws();
      if (text[i] === '.') i++;
      else return parts;
    }
  };

  const parseValue = (): unknown => {
    ws();
    const c = text[i];
    if (c === '"' || c === "'") return parseString();
    if (c === '[') {
      i++;
      const arr: unknown[] = [];
      for (;;) {
        wsNl();
        if (text[i] === ']') {
          i++;
          return arr;
        }
        arr.push(parseValue());
        wsNl();
        if (text[i] === ',') i++;
        else if (text[i] !== ']') fail('expected , or ] in array');
      }
    }
    if (c === '{') {
      i++;
      const obj: Obj = table();
      ws();
      if (text[i] === '}') {
        i++;
        return obj;
      }
      for (;;) {
        const key = parseKey();
        if (text[i] !== '=') fail('expected = in inline table');
        i++;
        setPath(obj, key, parseValue());
        ws();
        if (text[i] === ',') i++;
        else if (text[i] === '}') {
          i++;
          return obj;
        } else fail('expected , or } in inline table');
      }
    }
    const m = /^[^\s,\]}#]+/.exec(text.slice(i));
    if (!m) fail('expected a value');
    const raw = m![0];
    i += raw.length;
    if (raw === 'true') return true;
    if (raw === 'false') return false;
    if (/^[+-]?(\d[\d_]*)(\.\d+)?([eE][+-]?\d+)?$/.test(raw)) return Number(raw.replace(/_/g, ''));
    return raw; // dates and anything else stay strings
  };

  // Step into o[k], creating a table if absent. Only own properties are followed, and a
  // non-table value in the way is a parse error rather than something to write through.
  const descend = (o: Obj, k: string): Obj => {
    if (!Object.hasOwn(o, k)) o[k] = table();
    const next = Array.isArray(o[k]) ? o[k][o[k].length - 1] : o[k];
    if (next === null || typeof next !== 'object') fail(`key "${k}" is not a table`);
    return next as Obj;
  };

  const setPath = (obj: Obj, path: string[], value: unknown) => {
    let o = obj;
    for (const k of path.slice(0, -1)) o = descend(o, k);
    o[path[path.length - 1]!] = value;
  };

  const tableAt = (path: string[], arrayTable: boolean): Obj => {
    let o = root;
    path.forEach((k, idx) => {
      const last = idx === path.length - 1;
      if (last && arrayTable) {
        if (!Object.hasOwn(o, k) || !Array.isArray(o[k])) o[k] = [];
        const t: Obj = table();
        o[k].push(t);
        o = t;
        return;
      }
      o = descend(o, k);
    });
    return o;
  };

  for (;;) {
    wsNl();
    if (i >= n) break;
    if (text[i] === '[') {
      const arrayTable = text[i + 1] === '[';
      i += arrayTable ? 2 : 1;
      const path = parseKey();
      if (text[i] !== ']' || (arrayTable && text[i + 1] !== ']')) fail('expected ] after table name');
      i += arrayTable ? 2 : 1;
      current = tableAt(path, arrayTable);
      continue;
    }
    const key = parseKey();
    if (text[i] !== '=') fail('expected =');
    i++;
    setPath(current, key, parseValue());
    ws();
    if (text[i] === '#') while (i < n && text[i] !== '\n') i++;
    if (i < n && text[i] !== '\n' && text[i] !== '\r') fail('expected end of line');
  }
  return root;
}

// ---- Wrangler config -> LocalWorker ------------------------------------------------------

function routesOf(cfg: Obj): LocalWorker['routes'] {
  const list: unknown[] = [];
  if (cfg.route !== undefined) list.push(cfg.route);
  if (Array.isArray(cfg.routes)) list.push(...cfg.routes);
  return list.flatMap((r) => {
    if (typeof r === 'string') return [{ pattern: r, customDomain: false }];
    if (r && typeof r === 'object' && typeof (r as Obj).pattern === 'string') {
      return [{ pattern: (r as Obj).pattern as string, customDomain: (r as Obj).custom_domain === true }];
    }
    return [];
  });
}

function ratelimitsOf(cfg: Obj): LocalWorker['ratelimitNamespaces'] {
  const out: LocalWorker['ratelimitNamespaces'] = [];
  for (const b of Array.isArray(cfg.ratelimits) ? cfg.ratelimits : []) {
    if (b?.namespace_id !== undefined) out.push({ binding: String(b.name ?? ''), namespaceId: String(b.namespace_id) });
  }
  for (const b of Array.isArray(cfg.unsafe?.bindings) ? cfg.unsafe.bindings : []) {
    if (b?.type === 'ratelimit' && b.namespace_id !== undefined) out.push({ binding: String(b.name ?? ''), namespaceId: String(b.namespace_id) });
  }
  return out;
}

const bool = (v: unknown) => (typeof v === 'boolean' ? v : undefined);

function cronsOf(c: Obj | undefined): string[] | undefined {
  const list = c?.triggers?.crons;
  return Array.isArray(list) ? list.filter((x): x is string => typeof x === 'string') : undefined;
}

/**
 * One LocalWorker for the top level, and one per [env.<x>]: each environment is a separate
 * deployed Worker. Inheritable keys (compatibility_date, workers_dev, preview_urls, routes, triggers)
 * fall back to the top level; bindings are not inheritable, as in wrangler.
 */
export function workersFromConfig(cfg: Obj, file: string, authMarkers: string[] = []): LocalWorker[] {
  const name = typeof cfg.name === 'string' ? cfg.name : undefined;
  if (!name) return [];
  const make = (c: Obj, workerName: string, env?: string, parent?: Obj): LocalWorker => {
    const routes = routesOf(c);
    const inherited = parent && routes.length === 0 && c.route === undefined && c.routes === undefined ? routesOf(parent) : routes;
    const workersDev = bool(c.workers_dev) ?? (parent ? bool(parent.workers_dev) : undefined);
    const previewUrls = bool(c.preview_urls) ?? (parent ? bool(parent.preview_urls) : undefined);
    const compat = (c.compatibility_date ?? parent?.compatibility_date) as string | undefined;
    const crons = cronsOf(c) ?? cronsOf(parent);
    return {
      name: workerName,
      file,
      ...(env ? { env } : {}),
      ...(compat ? { compatibilityDate: String(compat) } : {}),
      ...(workersDev !== undefined ? { workersDev } : {}),
      ...(previewUrls !== undefined ? { previewUrls } : {}),
      routes: inherited,
      ratelimitNamespaces: ratelimitsOf(c),
      authMarkers,
      ...(crons?.length ? { crons } : {}),
    };
  };
  const out = [make(cfg, name)];
  if (cfg.env && typeof cfg.env === 'object') {
    for (const [env, ec] of Object.entries(cfg.env as Obj)) {
      if (!ec || typeof ec !== 'object') continue;
      out.push(make(ec as Obj, typeof (ec as Obj).name === 'string' ? (ec as Obj).name : `${name}-${env}`, env, cfg));
    }
  }
  return out;
}

export function parseWranglerFile(file: string, text: string, authMarkers: string[] = []): LocalWorker[] {
  const cfg = file.endsWith('.toml') ? parseToml(text) : parseJsonc(text);
  return workersFromConfig(cfg, file, authMarkers);
}

/** What counts as "this Worker does its own sign-in". Overridable in the config file. */
export const DEFAULT_AUTH_MARKERS: { label: string; pattern: string }[] = [
  { label: 'Access JWT check', pattern: 'cf-access-jwt-assertion' },
  { label: 'passkey / WebAuthn', pattern: 'navigator\\.credentials|webauthn|passkey' },
  { label: 'sign-in route', pattern: "['\"`]/(login|signin|sign-in|auth/callback)['\"`/]" },
  { label: 'email allowlist', pattern: 'allowed_emails' },
  { label: 'basic auth', pattern: 'www-authenticate' },
];
