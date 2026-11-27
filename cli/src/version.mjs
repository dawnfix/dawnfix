// The release this CLI belongs to: the reusable workflows it writes callers for, the
// templates and infra it links to, and the PyPI package dawnfix of the same version.
/* global __DAWNFIX_VERSION__ */
export const VERSION = typeof __DAWNFIX_VERSION__ === 'string' ? __DAWNFIX_VERSION__ : '0.0.0-dev';
export const TAG = `v${VERSION}`;
/** The moving major tag a caller uses by default (v0 for 0.x). */
export const MAJOR_REF = `v${VERSION.split('.')[0]}`;
export const REPO_URL = 'https://github.com/dawnfix/dawnfix';
export const RAW = `https://raw.githubusercontent.com/dawnfix/dawnfix/${TAG}`;
