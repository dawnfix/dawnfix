// Writing inside the repo, never through a symlink and never outside it. Every target and
// each of its parent directories up to the repo root is lstat'ed: a symlink there (dangling
// or not) is refused. New files are created with O_EXCL | O_NOFOLLOW; an overwrite (--force)
// is re-checked right before it and written with O_NOFOLLOW.
import { closeSync, constants, lstatSync, mkdirSync, openSync, realpathSync, writeSync } from 'node:fs';
import { dirname, isAbsolute, join, relative, sep } from 'node:path';

export class UnsafePath extends Error {}

function lstatOrNull(p) {
  try {
    return lstatSync(p);
  } catch (e) {
    if (e.code === 'ENOENT') return null;
    throw e;
  }
}

/** Checks one repo-relative path; returns { full, exists }. Throws UnsafePath. */
export function checkTarget(root, rel) {
  if (!rel || isAbsolute(rel) || rel.split(/[\\/]/).includes('..')) throw new UnsafePath(`${rel}: not a plain path inside the repo`);
  const realRoot = realpathSync(root);
  const full = join(root, rel);
  const parts = rel.split(/[\\/]/);
  let cur = root;
  let exists = false;
  for (let i = 0; i < parts.length; i++) {
    cur = join(cur, parts[i]);
    const st = lstatOrNull(cur);
    const shown = parts.slice(0, i + 1).join('/');
    if (st?.isSymbolicLink()) throw new UnsafePath(`${shown} is a symbolic link; refusing to write through it`);
    if (i < parts.length - 1 && st && !st.isDirectory()) throw new UnsafePath(`${shown} is not a directory`);
    if (i === parts.length - 1) {
      if (st && !st.isFile()) throw new UnsafePath(`${shown} exists and is not a regular file`);
      exists = Boolean(st);
    }
  }
  // The deepest existing parent must resolve inside the repo.
  let parent = dirname(full);
  while (!lstatOrNull(parent)) parent = dirname(parent);
  const realParent = realpathSync(parent);
  if (realParent !== realRoot && !realParent.startsWith(realRoot + sep)) {
    throw new UnsafePath(`${rel}: resolves outside the repo (${relative(realRoot, realParent)})`);
  }
  return { full, exists };
}

/** Writes text to repo-relative rel; overwrite only when allowed. */
export function safeWrite(root, rel, text, { overwrite = false } = {}) {
  const { full, exists } = checkTarget(root, rel);
  if (exists && !overwrite) throw new UnsafePath(`${rel} exists already`);
  // Parents one level at a time, each re-checked: no symlink can appear in between unseen.
  const parts = rel.split(/[\\/]/).slice(0, -1);
  let cur = root;
  for (const p of parts) {
    cur = join(cur, p);
    if (!lstatOrNull(cur)) mkdirSync(cur);
    if (lstatSync(cur).isSymbolicLink()) throw new UnsafePath(`${relative(root, cur)} is a symbolic link; refusing to write through it`);
  }
  const { exists: nowExists } = checkTarget(root, rel);
  const flags = constants.O_WRONLY | constants.O_NOFOLLOW | (nowExists ? constants.O_TRUNC : constants.O_CREAT | constants.O_EXCL);
  if (nowExists && !overwrite) throw new UnsafePath(`${rel} exists already`);
  const fd = openSync(full, flags, 0o644);
  try {
    writeSync(fd, text);
  } finally {
    closeSync(fd);
  }
}
