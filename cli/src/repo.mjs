// What init and doctor need to know about the repo they run in, from git alone.
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

export function git(cwd, ...args) {
  try {
    return execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch {
    return '';
  }
}

/** owner/repo from a GitHub remote URL (https, ssh or git@), or ''. */
export function slugFromRemote(url) {
  const m = /github\.com[:/]+([A-Za-z0-9][A-Za-z0-9-]*)\/([A-Za-z0-9_.-]+?)(?:\.git)?\/?$/.exec(url || '');
  return m ? `${m[1]}/${m[2]}` : '';
}

export function detectRepo(cwd) {
  const root = git(cwd, 'rev-parse', '--show-toplevel');
  if (!root) return null;
  const slug = slugFromRemote(git(root, 'remote', 'get-url', 'origin'));
  const head = git(root, 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD').replace(/^origin\//, '');
  const branch = head || git(root, 'symbolic-ref', '--short', 'HEAD') || 'main';
  return { root, slug, branch };
}

/** Best guesses for test.command and the install command, from the files at the repo root. */
export function detectCommands(root) {
  const has = (f) => existsSync(join(root, f));
  if (has('package.json')) {
    const install = has('pnpm-lock.yaml') ? 'pnpm install --frozen-lockfile' : has('yarn.lock') ? 'yarn install --frozen-lockfile' : has('package-lock.json') ? 'npm ci' : 'npm install';
    const test = has('pnpm-lock.yaml') ? 'pnpm test' : has('yarn.lock') ? 'yarn test' : 'npm test';
    return { test, install };
  }
  if (has('pyproject.toml') || has('requirements.txt')) {
    return { test: 'python -m pytest -q', install: has('requirements.txt') ? 'pip install -r requirements.txt' : 'pip install -e .' };
  }
  if (has('go.mod')) return { test: 'go test ./...', install: 'go mod download' };
  if (has('Cargo.toml')) return { test: 'cargo test', install: 'cargo fetch' };
  if (has('Gemfile')) return { test: 'bundle exec rake test', install: 'bundle install' };
  return { test: '', install: '' };
}
