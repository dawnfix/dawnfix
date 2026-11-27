// The secret-name baseline between runs. On a Worker this would be one KV key; here it is a
// JSON file. It holds account ids, script names and secret NAMES. No values.

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';

export interface State {
  version: 1;
  savedAt: string;
  secrets: Record<string, string[]>;
}

export async function loadState(file: string): Promise<State | undefined> {
  try {
    const s = JSON.parse(await readFile(file, 'utf8')) as State;
    return s.version === 1 && s.secrets && typeof s.secrets === 'object' ? s : undefined;
  } catch {
    return undefined;
  }
}

export async function saveState(file: string, secrets: Record<string, string[]>, now: Date): Promise<void> {
  await mkdir(dirname(file), { recursive: true });
  const s: State = { version: 1, savedAt: now.toISOString(), secrets };
  await writeFile(file, JSON.stringify(s, null, 2) + '\n', { mode: 0o600 });
}
