// Finds wrangler files under the repos given and reads them. Node only.

import { readdir, readFile, stat } from 'node:fs/promises';
import { homedir } from 'node:os';
import { basename, dirname, join, relative, resolve } from 'node:path';
import { DEFAULT_AUTH_MARKERS, parseWranglerFile } from '../core/wrangler.js';
import type { CoverageGap, LocalWorker } from '../core/types.js';

const CONFIG_NAMES = ['wrangler.jsonc', 'wrangler.json', 'wrangler.toml'];
const SKIP_DIRS = new Set(['node_modules', '.git', 'dist', 'build', '.wrangler', '.next', '.turbo', 'coverage', '.venv', 'vendor']);
const SOURCE_EXT = /\.(ts|tsx|js|mjs|jsx|cjs)$/;
const MAX_DEPTH = 4;
const MAX_SOURCE_FILES = 800;
const MAX_FILE_BYTES = 1_000_000;

export function expandHome(p: string): string {
  return p === '~' ? homedir() : p.startsWith('~/') ? join(homedir(), p.slice(2)) : p;
}

/** Expands a trailing "*" segment ("~/dev/*") for when the shell did not. */
export async function expandRepoArgs(args: string[]): Promise<string[]> {
  const out: string[] = [];
  for (const raw of args) {
    const p = resolve(expandHome(raw));
    if (basename(p) === '*') {
      const parent = dirname(p);
      try {
        for (const e of await readdir(parent, { withFileTypes: true })) if (e.isDirectory() && !e.name.startsWith('.')) out.push(join(parent, e.name));
      } catch {
        /* reported below as a gap when nothing is found */
      }
    } else out.push(p);
  }
  return [...new Set(out)];
}

async function findConfigs(dir: string, depth = 0): Promise<string[]> {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return [];
  }
  const found: string[] = [];
  // One config per directory, preferring jsonc as wrangler does.
  const here = CONFIG_NAMES.find((n) => entries.some((e) => e.isFile() && e.name === n));
  if (here) found.push(join(dir, here));
  if (depth >= MAX_DEPTH) return found;
  for (const e of entries) {
    if (e.isDirectory() && !SKIP_DIRS.has(e.name) && !e.name.startsWith('.')) found.push(...(await findConfigs(join(dir, e.name), depth + 1)));
  }
  return found;
}

async function sourceFiles(dir: string, acc: string[] = [], depth = 0): Promise<string[]> {
  if (acc.length >= MAX_SOURCE_FILES || depth > 8) return acc;
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return acc;
  }
  for (const e of entries) {
    if (acc.length >= MAX_SOURCE_FILES) break;
    const p = join(dir, e.name);
    if (e.isDirectory() && !SKIP_DIRS.has(e.name) && !e.name.startsWith('.')) await sourceFiles(p, acc, depth + 1);
    else if (e.isFile() && SOURCE_EXT.test(e.name) && !e.name.endsWith('.d.ts') && !/\.(test|spec)\./.test(e.name)) acc.push(p);
  }
  return acc;
}

// Handler definitions, not calls: `async fetch(req, env) {`, `fetch: app.fetch`, `{ fetch }`,
// addEventListener('fetch', ...). A call such as `await fetch(url)` is followed by `)` or `;`,
// never by a body, so it does not match.
const handlerRe = (name: string) =>
  new RegExp(
    `(?:^|[\\s,{;])(?:async\\s+)?${name}\\s*(?:\\([^)]*\\)\\s*(?::\\s*[^{;=]+)?\\{|:\\s*(?:async\\s+)?(?:function\\b|\\(|[A-Za-z_$][\\w$.]*\\s*[,}\\n]))` +
      `|[{,]\\s*${name}\\s*[,}]|addEventListener\\(\\s*['"\`]${name}['"\`]`,
    'm',
  );
const FETCH_RE = handlerRe('fetch');
const SCHEDULED_RE = handlerRe('scheduled');
/** `export default app` / `export default new Hono()`: an object whose fetch the search cannot see. */
const OPAQUE_DEFAULT_RE = /export\s+default\s+(?!\{|class\b|async\b|function\b)[A-Za-z_$]/;

export interface SourceScan {
  /** Labels of the auth markers found. */
  markers: string[];
  entry?: { fetch: boolean; scheduled: boolean; opaqueDefault: boolean };
}

/** Auth markers and handler hints in the source under a Worker's directory. */
export async function scanSource(dir: string, markers = DEFAULT_AUTH_MARKERS): Promise<SourceScan> {
  const res = markers.map((m) => ({ label: m.label, re: new RegExp(m.pattern, 'i') }));
  const hit = new Set<string>();
  const entry = { fetch: false, scheduled: false, opaqueDefault: false };
  let read = 0;
  for (const f of await sourceFiles(dir)) {
    try {
      if ((await stat(f)).size > MAX_FILE_BYTES) continue;
      const text = await readFile(f, 'utf8');
      read++;
      for (const m of res) if (!hit.has(m.label) && m.re.test(text)) hit.add(m.label);
      entry.fetch ||= FETCH_RE.test(text);
      entry.scheduled ||= SCHEDULED_RE.test(text);
      entry.opaqueDefault ||= OPAQUE_DEFAULT_RE.test(text);
    } catch {
      /* unreadable file: skip */
    }
  }
  return { markers: [...hit], ...(read ? { entry } : {}) };
}

/** Labels of the auth markers found in the source under a Worker's directory. */
export async function findAuthMarkers(dir: string, markers = DEFAULT_AUTH_MARKERS): Promise<string[]> {
  return (await scanSource(dir, markers)).markers;
}

export async function scanRepos(
  repos: string[],
  opts: { markers?: { label: string; pattern: string }[]; base?: string } = {},
): Promise<{ workers: LocalWorker[]; gaps: CoverageGap[]; files: string[] }> {
  const workers: LocalWorker[] = [];
  const gaps: CoverageGap[] = [];
  const files: string[] = [];
  const base = opts.base ?? homedir();
  for (const repo of await expandRepoArgs(repos)) {
    for (const file of await findConfigs(repo)) {
      const shown = relative(base, file).startsWith('..') ? file : `~/${relative(base, file)}`;
      files.push(shown);
      try {
        const text = await readFile(file, 'utf8');
        const src = await scanSource(dirname(file), opts.markers);
        workers.push(...parseWranglerFile(shown, text, src.markers).map((w) => ({ ...w, file: shown, ...(src.entry ? { entry: src.entry } : {}) })));
      } catch (e) {
        gaps.push({ account: 'local', what: shown, reason: `could not parse: ${e instanceof Error ? e.message : String(e)}` });
      }
    }
  }
  if (repos.length && files.length === 0) gaps.push({ account: 'local', what: repos.join(' '), reason: 'no wrangler.jsonc, wrangler.json or wrangler.toml found' });
  return { workers, gaps, files };
}
