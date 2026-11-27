import { resolve } from 'node:path';
import { audit, collectSnapshot } from '../src/core/audit.js';
import { DEFAULT_OPTIONS, type AuditOptions, type LocalWorker, type Snapshot } from '../src/core/types.js';
import { fakeCloudflare, NOW, type FakeOptions } from './fixtures/cloudflare.js';

export const REPOS = resolve(import.meta.dirname, 'fixtures/repos');

export async function apiSnapshot(fake: FakeOptions = {}, local: LocalWorker[] = []): Promise<Snapshot> {
  const f = fakeCloudflare(fake);
  const { snapshot } = await collectSnapshot({ tokens: ['test-token'], fetch: f.fetch, local, now: NOW });
  return snapshot;
}

export function run(snap: Snapshot, opts: Partial<AuditOptions> = {}) {
  return audit(snap, { ...DEFAULT_OPTIONS, now: NOW, ...opts });
}

export const byCheck = (r: ReturnType<typeof run>, check: string) => r.result.findings.filter((f) => f.check === check);
