"""CI configuration the agent's change must never touch, beyond the fixed names (publish.CI_CONFIG):
every file the base commit's GitLab CI configuration pulls in with `include: local:` (or a
plain string include), followed recursively through the included files, globs and all. A
change to any of them changes what CI runs, so publish refuses it like .gitlab-ci.yml itself.

Read from the base commit (never the agent's tree). Paths with CI variables in them ($VAR) are
widened to a wildcard, so the guard errs on refusing."""
import re

import yaml

MAX_FILES = 200


class _Loader(yaml.SafeLoader):
    """Safe YAML that accepts GitLab's custom tags (!reference) as plain data."""


_Loader.add_multi_constructor("!", lambda loader, suffix, node: None)


def _parse(text: str):
    try:
        return yaml.load(text, Loader=_Loader)  # noqa: S506 (a SafeLoader subclass)
    except yaml.YAMLError:
        return None


def _local_entries(doc) -> list[str]:
    """The local include paths of one CI file (remote, project, template, component skipped)."""
    if not isinstance(doc, dict) or "include" not in doc:
        return []
    inc = doc["include"]
    items = inc if isinstance(inc, list) else [inc]
    out = []
    for it in items:
        if isinstance(it, str):
            if not re.match(r"^[a-z]+://", it):
                out.append(it)
        elif isinstance(it, dict) and isinstance(it.get("local"), str):
            out.append(it["local"])
    return out


def pattern(path: str) -> re.Pattern:
    """A GitLab local include path as a regex over repo paths: `**` any depth, `*` and $VARs
    within one path segment."""
    p = path.strip().lstrip("/")
    rx, i = "", 0
    while i < len(p):
        if p.startswith("**", i):
            rx += ".*"
            i += 2
        elif p[i] == "*":
            rx += "[^/]*"
            i += 1
        elif p[i] == "$":
            m = re.match(r"\$\{?\w+\}?", p[i:])
            rx += "[^/]*"
            i += len(m.group(0)) if m else 1
        else:
            rx += re.escape(p[i])
            i += 1
    return re.compile(f"^{rx}$")


def included(read, tracked: list[str], roots=(".gitlab-ci.yml",)) -> list[re.Pattern]:
    """Patterns of every CI file reachable from the roots by local includes. `read(path)` gives
    a file's text at the base commit (or None); `tracked` lists the base commit's files."""
    pats = [pattern(r) for r in roots]
    seen, queue = set(), list(roots)
    while queue and len(seen) < MAX_FILES:
        f = queue.pop(0).lstrip("/")
        if f in seen:
            continue
        seen.add(f)
        text = read(f)
        if text is None:
            continue
        for entry in _local_entries(_parse(text)):
            rx = pattern(entry)
            pats.append(rx)
            queue += [t for t in tracked if rx.match(t) and t not in seen]
    return pats
