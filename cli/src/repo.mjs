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

/**
 * { host, path } of a GitLab remote URL (gitlab.com, or a self-managed host whose name contains
 * "gitlab"), with the full project path (group/subgroup/project); null for anything else.
 */
export function gitlabFromRemote(url) {
  const u = String(url || '').trim();
  // scheme://[user@]host[:port]/path  or  [user@]host:path (scp-like ssh)
  const m = /^[a-z][a-z0-9+.-]*:\/\/(?:[^@/]+@)?([^/:]+)(?::\d+)?\/(.+)$/i.exec(u) || /^(?:[^@/]+@)?([^/:]+):(?!\/\/)(.+)$/.exec(u);
  if (!m) return null;
  const host = m[1].toLowerCase();
  if (host !== 'gitlab.com' && !host.includes('gitlab')) return null;
  const path = m[2].replace(/\/+$/, '').replace(/\.git$/, '').replace(/^\/+/, '');
  if (!/^[A-Za-z0-9_.][A-Za-z0-9_.-]*(\/[A-Za-z0-9_.][A-Za-z0-9_.-]*)+$/.test(path)) return null;
  return { host, path };
}

/** { workspace, slug } of a bitbucket.org remote URL (https, ssh or git@), or null. */
export function bitbucketFromRemote(url) {
  const m = /^(?:[a-z][a-z0-9+.-]*:\/\/(?:[^@/]+@)?|(?:[^@/]+@)?)bitbucket\.org(?::\d+)?[:/]+([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+?)(?:\.git)?\/?$/i.exec(String(url || '').trim());
  return m ? { workspace: m[1], slug: m[2] } : null;
}

export function detectRepo(cwd) {
  const root = git(cwd, 'rev-parse', '--show-toplevel');
  if (!root) return null;
  const origin = git(root, 'remote', 'get-url', 'origin');
  const slug = slugFromRemote(origin);
  const gitlab = slug ? null : gitlabFromRemote(origin);
  const bitbucket = slug || gitlab ? null : bitbucketFromRemote(origin);
  const head = git(root, 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD').replace(/^origin\//, '');
  const branch = head || git(root, 'symbolic-ref', '--short', 'HEAD') || 'main';
  return { root, slug, gitlab, bitbucket, branch };
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
