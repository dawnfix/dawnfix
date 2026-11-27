// doctor's check of a Bitbucket repository's branch restrictions (no template import, so tests load it).
/** doctor: whether the branch restrictions hold a push restriction on `*` limited to listed accounts. */
export function pushRestrictionVerdict(values) {
  const r = (values || []).find((v) => v && v.kind === 'push' && v.pattern === '*'
    && (v.branch_match_kind || 'glob') === 'glob');
  if (!r) return { ok: false, why: 'no push restriction on * (every pipeline step can push through Bitbucket\'s git proxy)' };
  const who = [...(r.users || []).map((u) => u.display_name || u.uuid), ...(r.groups || []).map((g) => g.name || g.slug)];
  if (!who.length) return { ok: true, why: 'a push restriction on * that lets no account push (publish cannot push either)' };
  return { ok: true, why: `a push restriction on * lets only ${who.join(', ')} push` };
}
