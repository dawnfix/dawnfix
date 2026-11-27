"""The publish job's side of job isolation: the agent job's exported files (changes.json and
files/) turned into a patch in a fresh clone of the publish checkout, then handed to the same
validation as any patch (publish.stage_patch). Nothing in the artifact is trusted: each path is
checked to be a plain repo path and not .git or CI config, each file is read without following
a symlink (also as a parent directory) and must be a regular file; symlinks, special files and
binaries are refused, deletions of CI config too."""
import json
import os
import re
from pathlib import Path

from .gitsafe import git, out
from .scrub import say

SCHEMA = "dawnfix.run-files/1"


class FilesError(Exception):
    pass


def plain_path(rel) -> bool:
    if not isinstance(rel, str) or not rel or len(rel) > 4096 or "\0" in rel or "\\" in rel:
        return False
    if rel.startswith("/") or rel.endswith("/"):
        return False
    return all(p not in ("", ".", "..") for p in rel.split("/"))


def check_path(rel: str) -> None:
    from .publish import CI_CONFIG, WORKFLOWS, Refused
    if not plain_path(rel):
        raise Refused(f"name a path that is not a plain repo path ({rel!r})")
    if ".git" in rel.split("/") or any(p.lower() == ".git" for p in rel.split("/")):
        raise Refused(f"touch a .git path ({rel})")
    if WORKFLOWS.match(rel):
        raise Refused(f"touch a workflow ({rel})")
    if CI_CONFIG.match(rel):
        raise Refused(f"touch CI config ({rel})")


def load_changes(artifact: Path) -> dict:
    f = artifact / "changes.json"
    if not f.is_file() or f.is_symlink():
        raise FilesError("the artifact has no changes.json (the agent job's exported files)")
    try:
        doc = json.loads(f.read_text())
    except ValueError:
        doc = None
    if not (isinstance(doc, dict) and doc.get("schema") == SCHEMA and isinstance(doc.get("changed"), list)
            and isinstance(doc.get("deleted"), list)):
        raise FilesError(f"changes.json is not a {SCHEMA} document")
    return doc


def files_patch(checkout: Path, artifact: Path, base_sha: str, tmp: Path) -> bytes:
    """The exported files as a patch against base_sha, made in a fresh clone of the checkout."""
    from .agent import _no_symlink_parents, read_nofollow
    from .publish import Refused
    if not re.match(r"^[0-9a-f]{40}$", base_sha or ""):
        raise FilesError("meta.json has no base commit")
    doc = load_changes(artifact)
    src = artifact / "files"
    if src.is_symlink():
        raise Refused("add, change or remove a symlink or submodule (files)")
    fresh = tmp / "from-files"
    git("clone", "--quiet", "--no-local", "--no-hardlinks", "--no-checkout", str(checkout), str(fresh), cwd=tmp)
    kw = dict(cwd=fresh)
    git("checkout", "-q", "--detach", base_sha, **kw)
    if out("rev-parse", "HEAD", **kw) != base_sha:
        raise FilesError("the fresh clone is not at the base commit")
    tracked = {}
    for rec in git("ls-files", "-s", "-z", text=False, **kw).stdout.split(b"\0"):
        if rec:
            meta, rel = rec.decode("utf-8", "surrogateescape").split("\t", 1)
            tracked[rel] = meta.split()[0]

    def target(rel):
        if not _no_symlink_parents(fresh, rel, missing_ok=True):
            raise Refused(f"add, change or remove a symlink or submodule ({rel})")
        for i in range(1, len(rel.split("/"))):  # a parent that is a submodule or a tracked file
            if tracked.get("/".join(rel.split("/")[:i])) in ("160000", "120000", "100644", "100755"):
                raise Refused(f"add, change or remove a symlink or submodule ({rel})")
        if tracked.get(rel) in ("120000", "160000") or (fresh / rel).is_symlink():
            raise Refused(f"add, change or remove a symlink or submodule ({rel})")
        return fresh / rel

    # New files the base commit's .gitignore ignores (build output, __pycache__, node_modules)
    # are left out, as the namespace capture leaves them out (git ls-files --exclude-standard).
    # Read before anything is written, so a .gitignore the agent changed has no say.
    entries = [e for e in doc["changed"] if isinstance(e, dict)]
    if len(entries) != len(doc["changed"]):
        raise Refused("name a change that is not an object")
    new = [e.get("path") for e in entries if plain_path(e.get("path")) and e.get("path") not in tracked]
    ignored = set()
    if new:
        p = git("check-ignore", "-z", "--stdin", input_=("\0".join(new) + "\0").encode(), check=False,
                text=False, **kw)
        ignored = {x.decode("utf-8", "surrogateescape") for x in p.stdout.split(b"\0") if x}
    if ignored:
        say(f"notice: {len(ignored)} new file(s) the repo's .gitignore ignores were left out")
    seen = set()
    for e in entries:
        rel = e.get("path")
        check_path(rel)
        if rel in seen:
            raise Refused(f"name a path twice ({rel})")
        seen.add(rel)
        if rel in ignored:
            continue
        kind = e.get("kind")
        if kind in ("symlink", "special", "unreadable"):
            raise Refused(f"add, change or remove a symlink or submodule ({rel})")
        if kind != "file":
            raise Refused(f"name a change of an unknown kind ({rel})")
        data, exe = read_nofollow(src, rel)  # regular file, no symlink anywhere, not binary, <= 5 MB
        dst = target(rel)
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            dst.chmod(0o755 if exe else 0o644)
        except OSError:
            raise Refused(f"name a path that cannot be a file in this repo ({rel})") from None
    for rel in doc["deleted"]:
        check_path(rel)
        if rel in seen:
            raise Refused(f"name a path as both changed and deleted ({rel})")
        dst = target(rel)
        if os.path.lexists(dst):
            try:
                dst.unlink()
            except OSError:
                raise Refused(f"delete a path that is not a file ({rel})") from None
    git("add", "-A", "--", ".", **kw)
    return git("diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames", base_sha,
               text=False, **kw).stdout
