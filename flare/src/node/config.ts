// flare.config.json: what is public on purpose, what signs users in itself, thresholds,
// and which environment variables hold the tokens. Tokens themselves never go in here.

import { readFile } from 'node:fs/promises';
import { DEFAULT_OPTIONS } from '../core/types.js';

export interface FileConfig {
  publicHostnames?: string[];
  appAuthScripts?: string[];
  staleDays?: number;
  compatMonths?: number;
  accounts?: string[];
  tokenEnv?: string[];
  repos?: string[];
  authMarkers?: { label: string; pattern: string }[];
  failOn?: string;
}

const KEYS = new Set(['publicHostnames', 'appAuthScripts', 'staleDays', 'compatMonths', 'accounts', 'tokenEnv', 'repos', 'authMarkers', 'failOn', '$schema', '//']);

export function validateConfig(raw: unknown, file: string): FileConfig {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error(`${file}: expected a JSON object`);
  const o = raw as Record<string, unknown>;
  if ('token' in o || 'apiToken' in o) throw new Error(`${file}: put tokens in environment variables and list their names in tokenEnv`);
  for (const k of Object.keys(o)) if (!KEYS.has(k)) throw new Error(`${file}: unknown key "${k}"`);
  const strs = (k: string) => {
    if (o[k] !== undefined && (!Array.isArray(o[k]) || !(o[k] as unknown[]).every((x) => typeof x === 'string'))) throw new Error(`${file}: ${k} must be an array of strings`);
  };
  ['publicHostnames', 'appAuthScripts', 'accounts', 'tokenEnv', 'repos'].forEach(strs);
  for (const k of ['staleDays', 'compatMonths']) if (o[k] !== undefined && (typeof o[k] !== 'number' || (o[k] as number) <= 0)) throw new Error(`${file}: ${k} must be a positive number`);
  if (o.authMarkers !== undefined) {
    const m = o.authMarkers;
    if (!Array.isArray(m) || !m.every((x) => x && typeof x.label === 'string' && typeof x.pattern === 'string')) throw new Error(`${file}: authMarkers must be [{ "label", "pattern" }]`);
    for (const x of m) new RegExp(x.pattern, 'i');
  }
  return o as FileConfig;
}

export async function loadConfig(file: string | undefined, required: boolean): Promise<FileConfig> {
  if (!file) return {};
  let text: string;
  try {
    text = await readFile(file, 'utf8');
  } catch {
    if (required) throw new Error(`config file not found: ${file}`);
    return {};
  }
  return validateConfig(JSON.parse(text), file);
}

export { DEFAULT_OPTIONS };
