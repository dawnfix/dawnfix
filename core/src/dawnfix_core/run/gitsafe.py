"""git with nothing of the repo's or the machine's own config that could run code or redirect
a push: no global or system config, no system attributes, no hooks, no fsmonitor, no
attributes file, and attributes read from the empty tree (so no .gitattributes in a work tree
can name a filter or diff driver), in a minimal environment with no secret in it. The
reusable workflow's capture, commit and push hardening, and then some."""
import os
import re
import shutil
import subprocess

from .scrub import REDACT

GIT = shutil.which("git") or "git"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
SAFE = ("-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "core.attributesFile=/dev/null",
        f"--attr-source={EMPTY_TREE}")
# Only these reach git. No token, key or credential variable ever does.
PASS = ("PATH", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT")


class GitError(Exception):
    pass


def git_env(index: str | None = None, extra: dict | None = None) -> dict:
    env = {k: os.environ[k] for k in PASS if k in os.environ}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_ATTR_NOSYSTEM": "1",
                "GIT_TERMINAL_PROMPT": "0",
                "HOME": os.devnull, "GIT_ASKPASS": "", "SSH_ASKPASS": ""})
    if index:
        env["GIT_INDEX_FILE"] = index
    env.update(extra or {})
    return env


def check_version() -> None:
    """--attr-source needs git 2.42 or newer; older git is refused rather than run unsafely."""
    v = subprocess.run([GIT, "--version"], capture_output=True, text=True).stdout
    m = re.search(r"(\d+)\.(\d+)", v)
    if not m or (int(m.group(1)), int(m.group(2))) < (2, 42):
        raise GitError(f"git 2.42 or newer is needed (found: {v.strip() or 'none'})")


def git(*args, cwd=".", git_dir=None, work_tree=None, index=None, check=True, text=True, config=(),
        env_extra=None, input_=None) -> subprocess.CompletedProcess:
    cmd = [GIT, *SAFE]
    for c in config:
        cmd += ["-c", c]
    if git_dir:
        cmd.append(f"--git-dir={git_dir}")
    if work_tree:
        cmd.append(f"--work-tree={work_tree}")
    cmd += list(args)
    p = subprocess.run(cmd, cwd=cwd, env=git_env(index, env_extra), capture_output=True, text=text,
                       input=(input_.decode() if text and input_ is not None else input_))
    if check and p.returncode != 0:
        err = p.stderr if text else p.stderr.decode("utf-8", "replace")
        raise GitError(REDACT(f"git {args[0]} failed: {err.strip()}"))
    return p


def out(*args, **kw) -> str:
    return git(*args, **kw).stdout.strip()
