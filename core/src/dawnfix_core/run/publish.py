"""dawnfix run publish: the agent's artifact, published from a fresh checkout. The same rules
as the reusable workflow's publish job (Commit, then Publish), for any CI and, through a
HostAdapter, any supported repo host.

  1. The checkout must be the commit the agent started from (meta.json base_sha).
  2. The patch is refused outright if it touches .git or CI config (.github/workflows/**,
     .gitlab-ci.yml, bitbucket-pipelines.yml, .circleci/**), holds a binary file, or adds,
     changes or removes a symlink or submodule (by the old and new mode of every path).
  3. Each PR entry becomes two commits on dawnfix/<fingerprint> (the failing test, then the
     fix); protected paths, unchanged or doubly claimed files turn it into an issue; the full
     content of every changed file is scanned for credentials and for this run's secrets.
  4. The planned commits are pushed to an explicit URL (no remote, helper, include or hook
     of the checkout's config), and a DRAFT pull/merge request or an issue is opened. Never
     merged.

Only the repo host token (DAWNFIX_HOST_TOKEN) is in this stage's environment. git never sees
it except inside the push URL, and no output line ever shows it.
"""
import json
import re
import shutil
import tempfile
from pathlib import Path

from .. import config as cfg
from .gitsafe import GitError, check_version, git, out
from .guard import HASHES_FILE, GuardedHost, TextGuard, load_hashes
from .hosts import HostAdapter, HostError
from .scrub import CREDENTIAL_SHAPES, say

PROTECTED = re.compile(r"^(\.github/|\.dawnfix\.yml$|CODEOWNERS$|docs/CODEOWNERS$|\.claude/|\.mcp\.json$|"
                       r"\.gitmodules$|\.husky/|CLAUDE(\.local)?\.md$|\.dawnfix-run/|\.dawnfix-publish/|"
                       r"\.gitlab-ci\.yml$|\.gitlab/|bitbucket-pipelines\.yml$|\.circleci/|\.bitbucket/)")
WORKFLOWS = re.compile(r"^\.github/workflows/")
# CI config of every supported CI, conservatively: any *.gitlab-ci.yml, any YAML under a .gitlab/
# or ci/ directory, Bitbucket's file and .bitbucket/, CircleCI. (Files a GitLab config pulls in
# with include: local are refused too, ciconfig.py.)
CI_CONFIG = re.compile(r"^(bitbucket-pipelines\.yml$|\.circleci/|\.bitbucket/)|(^|/)[^/]*\.gitlab-ci\.ya?ml$|"
                       r"(^|/)(\.gitlab|ci)/(.*/)?[^/]*\.ya?ml$")
CREDENTIALS = re.compile("|".join(CREDENTIAL_SHAPES).encode())
FP = re.compile(r"^[0-9a-f]{16}$")
RISKY = re.compile(r"^(include\.|includeif\.|url\.|credential|http\.|protocol\.|core\.(sshcommand|askpass|gitproxy)$)", re.I)
COMMITTER = ("user.name=dawnfix", "user.email=dawnfix@users.noreply.github.com")


class Refused(Exception):
    """The agent's changes are refused outright; nothing is published."""


class PublishError(Exception):
    pass


def stage_patch(checkout: Path, patch: bytes, base_sha: str, tmp: Path) -> tuple[str, list[str]]:
    """Validate the patch and apply it to the index of the fresh checkout. Returns the snapshot
    tree and the changed paths; the work tree and index are back at base_sha afterwards."""
    kw = dict(cwd=checkout)
    if not re.match(r"^[0-9a-f]{40}$", base_sha or "") or out("rev-parse", "HEAD", **kw) != base_sha:
        raise PublishError("the checkout is not the commit the fix job started from; nothing published")
    if patch.strip():
        pf = tmp / "agent.patch"
        pf.write_bytes(patch)
        stats = git("apply", "--numstat", "-z", str(pf), text=False, **kw).stdout.split(b"\0")
        for rec in stats:
            if not rec:
                continue
            added, deleted, path = rec.decode("utf-8", "replace").split("\t", 2)
            if "/.git/" in f"/{path}/":
                raise Refused(f"touch a .git path ({path})")
            if WORKFLOWS.match(path):
                raise Refused(f"touch a workflow ({path})")
            if CI_CONFIG.match(path):
                raise Refused(f"touch CI config ({path})")
            if added == "-" and deleted == "-":
                raise Refused(f"include a binary file ({path})")
        # An early refusal on the patch's mode lines; the check after applying is the one that counts.
        if re.search(rb"^(new file mode|new mode|old mode|deleted file mode) (120000|160000)$", patch, re.M):
            raise Refused("add, change or remove a symlink or submodule")
        git("apply", "--cached", "--whitespace=nowarn", str(pf), **kw)
        raw = git("diff", "--cached", "--raw", "-z", "--no-renames", "HEAD", text=False, **kw).stdout.split(b"\0")
        for meta, path in zip(raw[0::2], raw[1::2]):
            if not meta:
                continue
            old_mode, new_mode = meta.decode().lstrip(":").split()[:2]
            if {old_mode, new_mode} & {"120000", "160000"}:
                raise Refused(f"add, change or remove a symlink or submodule ({path.decode('utf-8', 'replace')})")
    snap = out("write-tree", **kw)
    changed = [f for f in out("diff", "--cached", "--name-only", base_sha, **kw).splitlines() if f]
    for f in changed:
        if git("cat-file", "-e", f":{f}", check=False, **kw).returncode == 0:
            if b"\0" in git("cat-file", "-p", f":{f}", text=False, **kw).stdout:
                raise Refused(f"include a binary file ({f})")
    git("reset", "-q", "--hard", base_sha, **kw)
    return snap, changed


def _bad_paths(paths, changed, claimed) -> str:
    for f in paths:
        if not isinstance(f, str) or f in ("", "..") or f.startswith(("/", "../")) or "/../" in f or f.endswith("/.."):
            return f"path '{f}' is not a plain repo path"
        if PROTECTED.match(f):
            return f"path '{f}' is protected"
        if f not in changed:
            return f"path '{f}' was not changed"
        if f in claimed:
            return f"path '{f}' is claimed by another fingerprint"
    return ""


def _title(entry) -> str:
    t = "".join(c for c in str(entry.get("title") or "dawnfix finding") if 32 <= ord(c) < 127)[:100]
    return t or "dawnfix finding"


def _entries(result: dict, findings: dict):
    """Valid, known, first-seen entries of result.json, with the reasons others were skipped."""
    known = {f.get("fingerprint") for f in findings.get("findings", []) if isinstance(f, dict)}
    seen = set()
    for i, entry in enumerate(result["results"]):
        fp = entry.get("fingerprint", "") if isinstance(entry, dict) else ""
        if not isinstance(fp, str) or not FP.match(fp):
            say(f"warning: result entry {i} has no valid fingerprint; skipped")
            continue
        if fp not in known:
            say(f"warning: {fp} is not in findings.json; skipped")
            continue
        if fp in seen:
            say(f"warning: {fp} appears twice in result.json; second entry skipped")
            continue
        seen.add(fp)
        yield fp, entry


def load_result(run_dir: Path):
    result = run_dir / "result.json"
    if not result.is_file() or result.is_symlink():
        return None
    try:
        doc = json.loads(result.read_text())
    except ValueError:
        doc = None
    if not (isinstance(doc, dict) and doc.get("schema") == "dawnfix.result/1" and isinstance(doc.get("results"), list)):
        raise PublishError("result.json is not a dawnfix.result/1 document; nothing published")
    return doc


def _body(bodies: Path, src: Path, fp: str, footer: str) -> Path:
    b = bodies / f"{fp}.md"
    s = src / f"{fp}.md"
    text = s.read_text(errors="replace") if s.is_file() and not s.is_symlink() else "(no body written)\n"
    if f"dawnfix:fingerprint={fp}" not in text:
        text += f"\n<!-- dawnfix:fingerprint={fp} -->\n"
    b.write_text(text + footer)
    return b


def refuse_ci_includes(checkout: Path, base_sha: str, changed, ci_config_paths=()) -> None:
    """Refuse a change to any file the base commit's GitLab CI config includes (include: local,
    recursively, globs too), and to a custom CI config path the host names."""
    from .ciconfig import included
    kw = dict(cwd=checkout)
    tracked = [f for f in git("ls-tree", "-r", "--name-only", "-z", base_sha, text=False, **kw).stdout
               .decode("utf-8", "surrogateescape").split("\0") if f]

    def read(path):
        p = git("cat-file", "-p", f"{base_sha}:{path}", check=False, text=False, **kw)
        return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else None
    roots = [".gitlab-ci.yml", *[c for c in ci_config_paths if c and "@" not in c and "://" not in c]]
    pats = included(read, tracked, roots)
    for f in changed:
        if any(rx.match(f) for rx in pats):
            raise Refused(f"touch CI config ({f}, included by the CI configuration)")


def plan_fix(checkout: Path, artifact: Path, findings: dict, base_sha: str, autonomy: str, test_cmd: str | None,
             budget: int, run_url: str, bodies: Path, tmp: Path, guard: TextGuard | None = None,
             patch: bytes | None = None, ci_config_paths=(), commit_note: str = ""):
    """The Commit step: commits made, a plan of PRs and issues, and whether anything failed.
    commit_note: a line added to each commit message (Bitbucket: "[skip ci]")."""
    plan, failed = [], False
    result = load_result(artifact / "run")
    if result is None:
        say("warning: the fix run wrote no result.json; nothing published")
        return plan, failed
    if patch is None:
        patch_file = artifact / "agent.patch"
        patch = patch_file.read_bytes() if patch_file.is_file() and not patch_file.is_symlink() else b""
    snap, changed = stage_patch(checkout, patch, base_sha, tmp)
    refuse_ci_includes(checkout, base_sha, changed, ci_config_paths)
    kw = dict(cwd=checkout)
    claimed, prs = set(), 0

    def take(paths):
        for f in paths:
            if git("cat-file", "-e", f"{snap}:{f}", check=False, **kw).returncode == 0:
                git("checkout", "-q", snap, "--", f, **kw)
            else:
                git("rm", "-q", "--cached", "--ignore-unmatch", "--", f, **kw)
                (checkout / f).unlink(missing_ok=True)

    def commit(msg):
        note = ["-m", commit_note] if commit_note else []
        git("commit", "-q", "--no-verify", "-m", msg, *note, config=COMMITTER, **kw)

    footer = f"\n\n---\nOpened by Dawnfix. AI-generated: review before merging. Run: {run_url}\n"
    for fp, entry in _entries(result, findings):
        action = entry.get("action") or "none"
        title = guard.title(_title(entry)) if guard else _title(entry)  # also the commit subjects
        body = _body(bodies, artifact / "run", fp, footer)
        if action not in ("pr", "issue", "none"):
            say(f"error: {fp}: unknown action '{action}'")
            failed = True
            continue
        if action == "none":
            say(f"{fp}: nothing to publish")
            continue
        tests = [f for f in entry.get("test_files") or [] ]
        fixes = [f for f in entry.get("fix_files") or [] ]
        if action == "pr":
            why = ""
            if autonomy != "draft-pr":
                why = f"autonomy is {autonomy}"
            elif not test_cmd:
                why = "no test.command in .dawnfix.yml, so no failing test could be run"
            elif prs >= budget:
                why = "limits.fix_prs_per_day reached"
            elif not tests or not fixes:
                why = "result.json needs both test_files and fix_files"
            else:
                why = _bad_paths(tests + fixes, changed, claimed)
                if not why:
                    both = [t for t in tests if t in fixes]
                    if both:
                        why = f"path '{both[0]}' is in both test_files and fix_files"
            if "is protected" in why:
                say(f"error: {fp}: the fix touched protected paths ({why}); nothing pushed")
                failed = True
            if why:
                say(f"{fp}: reporting as an issue instead of a PR: {why}")
                with open(body, "a") as f:
                    f.write(f"\n## Why no PR\n{why}\n")
                action = "issue"
        if action == "issue":
            plan.append({"fp": fp, "action": "issue", "title": title, "body": str(body)})
            continue
        branch = f"dawnfix/{fp}"
        git("checkout", "-q", "-B", branch, base_sha, **kw)
        take(tests)
        commit(f"test: reproduce {title} (dawnfix {fp})")
        take(fixes)
        commit(f"fix: {title} (dawnfix {fp})")
        # Nothing that looks like a credential, anywhere in the files this PR changes: the
        # whole file, not only the changed lines (matches are not printed).
        leak = any(git("cat-file", "-e", f"HEAD:{f}", check=False, **kw).returncode == 0 and
                   _leaks(git("cat-file", "-p", f"HEAD:{f}", text=False, **kw).stdout, guard)
                   for f in tests + fixes)
        if leak:
            say(f"error: {fp}: a changed file contains something that looks like a credential; nothing pushed")
            failed = True
            git("checkout", "-q", "--detach", base_sha, **kw)
            git("branch", "-q", "-D", branch, **kw)
            continue
        claimed.update(tests + fixes)
        prs += 1
        plan.append({"fp": fp, "action": "pr", "branch": branch, "title": title, "body": str(body),
                     "sha": out("rev-parse", "HEAD", **kw)})
        if entry.get("also_issue") is True:
            plan.append({"fp": fp, "action": "also-issue", "title": title, "body": str(body)})
        git("checkout", "-q", "--detach", base_sha, **kw)
    unclaimed = [f for f in changed if f not in claimed]
    if changed and unclaimed and prs:
        say(f"notice: changed files not claimed by any planned PR were dropped: {' '.join(unclaimed)}")
    return plan, failed


def _leaks(content: bytes, guard) -> bool:
    return bool(CREDENTIALS.search(content)) or bool(guard and guard.found(content))


def publish_plan(checkout: Path, plan: list, host: HostAdapter, token: str, issues: str, guard,
                 push_env: dict | None = None) -> tuple[list, bool]:
    """The Publish step: push exactly the planned commits, open the draft changes and issues."""
    failed = False
    opened = []
    if not plan:
        say("nothing to publish")
        return opened, failed
    kw = dict(cwd=checkout)
    base_sha = out("rev-parse", "HEAD", **kw)
    risky = [k for k in out("config", "--local", "--name-only", "--list", **kw).splitlines() if RISKY.match(k)]
    if risky:
        raise PublishError(f"the publish checkout's git config has settings that could redirect a push "
                           f"({' '.join(risky)}); nothing pushed")

    def publish_issue(fp, title, body):
        if issues not in cfg.HOST_ISSUES:
            say(f"report.issues is {issues}; issue for {fp} skipped")
            return
        text = Path(body).read_text()
        existing = host.find_existing(fp).issue
        if existing:
            host.comment(existing, text)
            say(f"{fp}: commented on open issue #{existing.number}")
        else:
            made = host.open_issue(f"dawnfix: {title} ({fp})", text)
            say(f"{fp}: written to the log above (no issue tracker)" if made.kind == "log" else f"{fp}: opened issue {made.url}")

    for e in plan:
        fp, action, title, body = e["fp"], e["action"], e["title"], e["body"]
        if action == "issue":
            publish_issue(fp, title, body)
            continue
        if action == "also-issue":
            url = next((o["url"] for o in opened if o["fingerprint"] == fp), "")
            if url:
                with open(body, "a") as f:
                    f.write(f"\nDraft PR: {url}\n")
                publish_issue(fp, title, body)
            continue
        branch, sha = e["branch"], e["sha"]
        prior = host.find_existing(fp).change
        if prior:
            if prior.state == "open":
                host.comment(prior, Path(body).read_text())
                say(f"{fp}: PR #{prior.number} is already open; commented the new analysis there")
            else:
                with open(body, "a") as f:
                    f.write(f"\n## Why no PR\na PR for this fingerprint was closed before (#{prior.number}); not recreated\n")
                say(f"{fp}: a PR for this fingerprint was closed before (#{prior.number}); reporting as an issue")
                publish_issue(fp, title, body)
            continue
        # None of this run's secret values in any file the branch changes (whole files).
        files = [f for f in out("diff", "--name-only", base_sha, branch, **kw).splitlines() if f]
        leak = False
        for f in files:
            p = git("cat-file", "-p", f"{branch}:{f}", check=False, text=False, **kw)
            content = p.stdout if p.returncode == 0 else b""
            if _leaks(content, guard):
                leak = True
        if leak:
            say(f"error: {fp}: the diff contains something that looks like a credential; nothing pushed")
            failed = True
            continue
        if not re.match(r"^[0-9a-f]{40}$", sha or "") or \
                git("rev-parse", "--verify", "-q", f"refs/heads/{branch}", check=False, **kw).stdout.strip() != sha:
            say(f"error: {fp}: {branch} is not the commit the Commit step made; nothing pushed")
            failed = True
            continue
        # credential.helper= empties the helper list; include.path=/dev/null adds nothing; the
        # checkout's own includes and redirects were refused above.
        opts = [a for o in host.push_options for a in ("-o", o)]
        p = git("push", "-q", "--no-verify", *opts, host.push_url(token), f"refs/heads/{branch}:refs/heads/{branch}",
                check=False, config=("credential.helper=", "include.path=/dev/null"), env_extra=push_env, **kw)
        if p.returncode != 0:
            say(f"warning: {fp}: push to {branch} failed (branch exists?); nothing opened")
            continue
        change = host.open_draft_change(branch, f"dawnfix: {title}", Path(body).read_text())
        opened.append({"fingerprint": fp, "url": change.url})
        say(f"{fp}: opened {change.url}")
    return opened, failed


def publish_diagnose(artifact: Path, findings: dict, host: HostAdapter, issues: str, run_url: str,
                     bodies: Path) -> tuple[int, bool]:
    """The diagnose job's "File issues" step: issues only, never git, never a pull request."""
    result = load_result(artifact / "run")
    if result is None:
        say("warning: the diagnose run wrote no result.json; nothing filed")
        return 0, False
    if issues not in cfg.HOST_ISSUES:
        say(f"report.issues is {issues}; the diagnose stage files repo host issues only, nothing filed")
        return 0, False
    filed = logged = 0
    footer = f"\n\n---\nDiagnosed by Dawnfix. AI-generated: verify before acting. Run: {run_url}\n"
    for fp, entry in _entries(result, findings):
        action = entry.get("action") or "none"
        if action == "none":
            say(f"{fp}: nothing to file")
            continue
        if action == "pr":
            say(f"notice: {fp}: the diagnose stage opens no pull requests; filed as an issue")
        elif action != "issue":
            say(f"warning: {fp}: unknown action '{action}'; skipped")
            continue
        src = artifact / "run" / f"{fp}.md"
        if src.is_symlink():
            say(f"warning: {fp}: the issue body is a symlink; skipped")
            continue
        body = _body(bodies, artifact / "run", fp, footer).read_text()
        existing = host.find_existing(fp).issue
        if existing:
            host.comment(existing, body)
            say(f"{fp}: commented on open issue #{existing.number}")
        else:
            made = host.open_issue(f"dawnfix: {_title(entry)} ({fp})", body)
            if made.kind == "log":
                logged += 1
            else:
                filed += 1
    say(f"dawnfix: {filed} new issue(s) filed" + (f", {logged} written to the log (no issue tracker)" if logged else ""))
    return filed, False


def artifact_patch(checkout: Path, artifact: Path, meta: dict, isolation: str, tmp: Path) -> bytes | None:
    """The agent's changes as a patch. From an agent job run with --isolation job: built here,
    from its exported files, in a fresh clone (files.files_patch). Otherwise its agent.patch.
    With --isolation job, an artifact holding a patch instead of files is refused."""
    from .files import FilesError, files_patch
    if meta.get("capture") == "files":
        try:
            return files_patch(checkout, artifact, meta.get("base_sha", ""), tmp)
        except FilesError as e:
            raise PublishError(f"{e}; nothing published") from None
    if isolation == "job":
        raise PublishError("this publish job takes the exported files of an agent job run with --isolation job, "
                           "and the artifact is not that; nothing published")
    return None


def run_publish(*, checkout: Path, artifact: Path, findings_path: Path, out_dir: Path, host: HostAdapter,
                token: str, secret_values=(), push_env=None, autonomy: str = "", config_path: Path | None = None,
                isolation: str = "namespace") -> int:
    meta_file = artifact / "meta.json"
    if not meta_file.is_file() or meta_file.is_symlink():
        raise PublishError(f"{artifact}: no meta.json; not an artifact of dawnfix run agent")
    meta = json.loads(meta_file.read_text())
    if meta.get("schema") != "dawnfix.run-agent/1" or meta.get("mode") not in ("fix", "diagnose"):
        raise PublishError("meta.json is not a dawnfix.run-agent/1 document")
    if isolation not in ("namespace", "job"):
        raise PublishError("--isolation must be namespace or job")
    findings = json.loads(findings_path.read_text())
    checkout = checkout.resolve()
    check_version()
    # Every text sent to the host is scanned: this stage's own secrets by value, the earlier
    # stages' by hash (the agent's artifact carries its own and the read stage's list).
    guard = TextGuard(values=[token, *host.auth_values, *secret_values], hashes=load_hashes(artifact / HASHES_FILE) +
                      load_hashes(findings_path.parent / HASHES_FILE))
    host = GuardedHost(host, guard)
    # The config of the fresh checkout at the base commit, not anything the agent wrote.
    conf = cfg.load(str(config_path or checkout / ".dawnfix.yml"))
    issues = conf.report["issues"]
    # Autonomy from this job (DAWNFIX_AUTONOMY) or the checkout's config, never from the
    # artifact: a process the agent left behind could have rewritten that.
    autonomy = autonomy or conf.autonomy
    if autonomy not in ("diagnose", "plan", "draft-pr"):
        raise PublishError(f"autonomy must be diagnose, plan or draft-pr, not '{autonomy}'")
    run_url = host.ci_context().run_url
    out_dir.mkdir(parents=True, exist_ok=True)
    bodies = out_dir / "bodies"
    shutil.rmtree(bodies, ignore_errors=True)
    bodies.mkdir()
    opened, failed = [], False
    with tempfile.TemporaryDirectory(prefix="dawnfix-publish-") as tmp:
        if meta["mode"] == "diagnose":
            _, failed = publish_diagnose(artifact, findings, host, issues, run_url, bodies)
        else:
            budget = max(0, int(conf.limits["fix_prs_per_day"]) - host.changes_opened_today())
            say(f"dawnfix PRs left today: {budget} of {int(conf.limits['fix_prs_per_day'])}")
            # The checkout must be the base commit before anything of the artifact is used.
            if out("rev-parse", "HEAD", cwd=checkout) != meta.get("base_sha"):
                raise PublishError("the checkout is not the commit the fix job started from; nothing published")
            patch = artifact_patch(checkout, artifact, meta, isolation, Path(tmp))
            plan, failed = plan_fix(checkout, artifact, findings, meta.get("base_sha", ""), autonomy,
                                    conf.test_command, budget, run_url, bodies, Path(tmp), guard, patch=patch,
                                    ci_config_paths=(host.ci_config_path(),), commit_note=host.commit_note)
            opened, failed2 = publish_plan(checkout, plan, host, token, issues, guard, push_env)
            failed = failed or failed2
    (out_dir / "opened.json").write_text(json.dumps({"schema": "dawnfix.opened/1", "opened": opened}, indent=2) + "\n")
    return 1 if failed else 0


__all__ = ["PublishError", "Refused", "GitError", "HostError", "run_publish", "stage_patch", "plan_fix",
           "publish_plan", "publish_diagnose", "PROTECTED", "CREDENTIALS"]
