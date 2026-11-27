import { describe, expect, it } from 'vitest';
import { parseJsonc, parseToml, parseWranglerFile } from '../src/core/wrangler.js';

describe('parseJsonc', () => {
  it('drops comments and trailing commas but keeps // inside strings', () => {
    expect(parseJsonc('{ "a": "http://x/y", // c\n /* b */ "b": [1,2,], }')).toEqual({ a: 'http://x/y', b: [1, 2] });
  });
});

describe('parseToml', () => {
  it('reads tables, arrays of tables, nested sub-tables and inline tables', () => {
    const t = parseToml(`
name = "w" # comment
n = 1_000
on = true
d = 2024-01-01
arr = [ "a", 'b', { x = 1 }, ]
[a.b]
c = "d"
[[list]]
k = 1
  [list.sub]
  s = "x"
[[list]]
k = 2
`);
    expect(t).toEqual({ name: 'w', n: 1000, on: true, d: '2024-01-01', arr: ['a', 'b', { x: 1 }], a: { b: { c: 'd' } }, list: [{ k: 1, sub: { s: 'x' } }, { k: 2 }] });
  });
  it('fails with a line number', () => {
    expect(() => parseToml('a = [1,\n')).toThrow(/TOML line/);
  });
});

describe('parseWranglerFile', () => {
  it('jsonc: routes, ratelimits and an absent workers_dev', () => {
    const [w] = parseWranglerFile('w.jsonc', '{"name":"x","compatibility_date":"2026-01-01","routes":["x.example.com/*",{"pattern":"y.example.com","custom_domain":true}],"ratelimits":[{"name":"L","namespace_id":"1001"}]}');
    expect(w).toEqual({
      name: 'x',
      file: 'w.jsonc',
      compatibilityDate: '2026-01-01',
      routes: [
        { pattern: 'x.example.com/*', customDomain: false },
        { pattern: 'y.example.com', customDomain: true },
      ],
      ratelimitNamespaces: [{ binding: 'L', namespaceId: '1001' }],
      authMarkers: [],
    });
  });
  it('toml: each [env.x] is its own Worker that inherits routes but not bindings', () => {
    const ws = parseWranglerFile(
      'w.toml',
      `name = "x"\nworkers_dev = false\nroute = "x.example.com/*"\n[[unsafe.bindings]]\ntype = "ratelimit"\nname = "L"\nnamespace_id = 5\n[env.dev]\nworkers_dev = true\n[env.prod]\nname = "x-live"\n`,
    );
    expect(ws.map((w) => [w.name, w.workersDev, w.routes.length, w.ratelimitNamespaces.length])).toEqual([
      ['x', false, 1, 1],
      ['x-dev', true, 1, 0],
      ['x-live', false, 1, 0],
    ]);
  });
  it('skips a config with no name', () => {
    expect(parseWranglerFile('w.jsonc', '{"main":"x.ts"}')).toEqual([]);
  });
});

describe('untrusted wrangler.toml cannot reach Object.prototype', () => {
  const payloads = [
    '[__proto__]\nbaseUrl = "https://evil.example"\n',
    '__proto__.baseUrl = "https://evil.example"\n',
    '[a.constructor.prototype]\nbaseUrl = "https://evil.example"\n',
    'x = { __proto__ = { baseUrl = "https://evil.example" } }\n',
    '[["__proto__"]]\nbaseUrl = "https://evil.example"\n',
    '"constructor" = 1\n',
  ];
  for (const p of payloads) {
    it(`refuses ${JSON.stringify(p.split('\n')[0])}`, () => {
      expect(() => parseToml(p)).toThrow(/forbidden key/);
      expect(({} as Record<string, unknown>).baseUrl).toBeUndefined();
    });
  }

  it('builds tables without a prototype and refuses writing through a value', () => {
    const t = parseToml('[env.staging]\nname = "x"\n');
    expect(Object.getPrototypeOf(t)).toBeNull();
    expect(Object.getPrototypeOf(t.env)).toBeNull();
    expect(() => parseToml('a = 1\n[a.b]\nc = 2\n')).toThrow(/not a table/);
  });
});
