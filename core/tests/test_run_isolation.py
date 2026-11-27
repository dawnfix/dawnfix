"""Job isolation (GitLab CI, Bitbucket Pipelines): the agent job runs no git and exports only
files; the publish job builds the patch itself in a fresh clone and applies every validation.
The agent job can never produce a git-applied change that publish did not check: whatever it
writes (a patch, CI config, a symlink, a binary, a .git path, a forged changes.json), the
publish stage refuses it or applies only what passes."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dawnfix_core.run import agent
from dawnfix_core.run.agent import AgentError, run_agent
from dawnfix_core.run.cli import main as run_main
from dawnfix_core.run.hosts import Change, Existing, HostAdapter
from dawnfix_core.run.context import detect
from dawnfix_core.run.publish import PublishError, Refused, run_publish

from .run_fakes import AI_KEY, FakeHttp

FP = "1997f26556fdd1c5"
TOKEN = "glpat" + "-" + "P" * 24
CONFIG = ("version: 1\nautonomy: draft-pr\nsources: [{aws: {region: us-east-1, alarms: true}}]\n"
          "limits: {fix_prs_per_day: 2, max_turns: 30}\ntest: {command: python3 -m pytest}\nreport: {issues: host}\n")
CTX = detect({"GITLAB_CI": "true", "CI_PROJECT_PATH": "acme/shop", "CI_PROJECT_ID": "1", "CI_SERVER_HOST": "gitlab.com",
              "CI_JOB_URL": "https://gitlab.com/acme/shop/-/jobs/5"})

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys
sys.stdin.read()
mode = os.environ.get("FAKE_MODE", "fix")
w = pathlib.Path(".")
(w / "tests" / "test_users.py").write_text("from app.users import name\n\ndef test_null():\n    assert name(None) == ''\n")
(w / "app" / "users.py").write_text("def name(u):\n    return (u or {}).get('name', '')\n")
if mode == "ci":
    (w / ".gitlab-ci.yml").write_text("steal:\n  script: [env]\n")
if mode == "ci-delete":
    (w / ".gitlab-ci.yml").unlink()
if mode == "symlink":
    (w / "app" / "link.py").symlink_to("/etc/passwd")
if mode == "pycache":
    (w / "app" / "__pycache__").mkdir()
    (w / "app" / "__pycache__" / "users.cpython-312.pyc").write_bytes(b"\x00pyc")
    (w / ".gitignore").write_text("")  # the agent's own .gitignore has no say
if mode == "binary":
    (w / "app" / "blob.bin").write_bytes(b"\x00\x01\x02")
if mode == "gitdir":
    (w / ".git" / "hooks").mkdir(parents=True, exist_ok=True)
    (w / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\ntouch /tmp/x\n")
    (w / "vendor" / ".git").mkdir(parents=True)
    (w / "vendor" / ".git" / "config").write_text("[core]\n\thooksPath = /tmp\n")
if mode == "patch":
    # A patch planted where the namespace capture would put it: never used in job mode.
    pathlib.Path(os.environ["FAKE_OUT"]).mkdir(parents=True, exist_ok=True)
if mode == "secret":
    (w / "app" / "users.py").write_text("KEY = '" + os.environ["ANTHROPIC" + "_API_KEY"] + "'\n")
if mode == "setsid":
    subprocess.Popen(["sh", "-c", "sleep 0.2; echo late >> app/late.py; sleep 30"], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
out = w / ".dawnfix-run" / "out"
(out / "result.json").write_text(json.dumps({"schema": "dawnfix.result/1", "results": [
    {"fingerprint": "1997f26556fdd1c5", "action": "pr", "title": "None user crashes name()",
     "test_files": ["tests/test_users.py"], "fix_files": ["app/users.py"]}]}))
(out / "1997f26556fdd1c5.md").write_text("## Cause\napp/users.py:2 reads .name of None\n")
'''


def sh(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}).stdout.strip()


class FakeHost(HostAdapter):
    name = "fake"
    push_options = ("ci.skip",)

    def __init__(self, push_to):
        super().__init__(CTX, TOKEN)
        self.push_to, self.calls = push_to, []

    def default_branch(self):
        return "main"

    def find_existing(self, fp):
        return Existing()

    def open_draft_change(self, branch, title, body):
        self.calls.append(("draft", branch, title, body))
        return Change("change", 1, "open", "https://gitlab.com/acme/shop/-/merge_requests/1")

    def open_issue(self, title, body, labels=("dawnfix", "AI-generated")):
        self.calls.append(("issue", title, body))
        return Change("issue", 2, "open", "https://gitlab.com/acme/shop/-/issues/2")

    def comment(self, change, body):
        self.calls.append(("comment", change.number, body))

    def changes_opened_today(self):
        return 0

    def push_url(self, token):
        return str(self.push_to)


@pytest.fixture
def s(tmp_path):
    origin = tmp_path / "origin"
    (origin / "app").mkdir(parents=True)
    (origin / "tests").mkdir()
    (origin / "app" / "users.py").write_text("def name(u):\n    return u['name']\n")
    (origin / "app" / "__init__.py").write_text("")
    (origin / "tests" / "__init__.py").write_text("")
    (origin / ".gitlab-ci.yml").write_text("include: []\n")
    (origin / ".gitignore").write_text("__pycache__/\n")
    (origin / ".dawnfix.yml").write_text(CONFIG)
    sh(origin, "init", "-q", "-b", "main")
    sh(origin, "add", "-A")
    sh(origin, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    bare = tmp_path / "remote.git"
    sh(tmp_path, "clone", "-q", "--bare", str(origin), str(bare))
    sh(bare, "config", "receive.advertisePushOptions", "true")
    # The agent job's tree: a tokenless archive of the commit, no .git (GIT_STRATEGY: none).
    work = tmp_path / "agent-job"
    export(origin, work)
    claude = tmp_path / "bin" / "claude"
    claude.parent.mkdir()
    claude.write_text(FAKE_CLAUDE)
    claude.chmod(0o755)
    findings = tmp_path / "read" / "findings.json"
    findings.parent.mkdir()
    findings.write_text(json.dumps({"findings": [{"fingerprint": FP}]}))
    prompt = "<!-- dawnfix:ci-prompt fix -->\n# Dawnfix CI: fix\n"
    http = FakeHttp({("GET", "https://raw.githubusercontent.com/dawnfix/dawnfix/"): (200, prompt)})
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home"), "DAWNFIX_AI_API_KEY": AI_KEY}
    return dict(tmp=tmp_path, bare=bare, work=work, claude=claude, findings=findings, http=http, env=env,
                base=sh(origin, "rev-parse", "HEAD"), origin=origin)


def export(origin, work):
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    tar = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=origin, check=True, capture_output=True).stdout
    subprocess.run(["tar", "-xf", "-", "-C", str(work)], input=tar, check=True)


def agent_job(s, fake="fix", no_git=None):
    out = s["tmp"] / "artifact"
    env = {**s["env"], "FAKE_MODE": fake, "FAKE_OUT": str(out)}
    rc = run_agent(mode="fix", workdir=s["work"], findings=s["findings"], out_dir=out,
                   config_path=s["work"] / ".dawnfix.yml", env=env, http=s["http"], claude_cmd=[str(s["claude"])],
                   pass_env=["FAKE_MODE", "FAKE_OUT"], isolation="job", base_commit=s["base"])
    return rc, out


def publish_job(s, art, isolation="job"):
    checkout = s["tmp"] / "publish-job"
    if not checkout.exists():
        sh(s["tmp"], "clone", "-q", str(s["bare"]), str(checkout))
    host = FakeHost(s["bare"])
    rc = run_publish(checkout=checkout, artifact=art, findings_path=s["findings"], out_dir=s["tmp"] / "pub",
                     host=host, token=TOKEN, isolation=isolation)
    return rc, host


def branches(s):
    return sh(s["bare"], "branch", "--list", "dawnfix/*")


@pytest.fixture
def no_git(monkeypatch):
    """Any git call from the agent stage fails the test: job isolation runs none."""
    def boom(*a, **k):
        raise AssertionError(f"the agent stage ran git {a[:1]}")
    for name in ("git", "out", "check_version"):
        monkeypatch.setattr(agent, name, boom)


# --- the agent job --------------------------------------------------------------------------
def test_the_agent_job_runs_no_git_and_exports_only_files(s, no_git):
    rc, art = agent_job(s)
    assert rc == 0
    assert not (art / "agent.patch").exists()
    meta = json.loads((art / "meta.json").read_text())
    assert (meta["isolation"], meta["capture"], meta["base_sha"]) == ("job", "files", s["base"])
    changes = json.loads((art / "changes.json").read_text())
    assert {c["path"] for c in changes["changed"]} == {"tests/test_users.py", "app/users.py"}
    assert changes["deleted"] == []
    assert (art / "files" / "app" / "users.py").read_text().startswith("def name(u):\n    return (u or {})")
    assert sorted(p.name for p in (art / "run").iterdir()) == [f"{FP}.md", "result.json"]
    # The secret hashes of this job (the AI key, the ambient CI job token), never the values.
    hashes = (art / "secret-hashes.json").read_text()
    assert AI_KEY not in hashes and "ambient-job-token-123" not in hashes


def test_the_agent_job_exports_what_publish_must_refuse_without_judging_it(s, no_git):
    for mode, expect in [("ci", (".gitlab-ci.yml", "file")), ("symlink", ("app/link.py", "symlink")),
                         ("binary", ("app/blob.bin", "file")), ("gitdir", ("vendor/.git/config", "file"))]:
        export(s["origin"], s["work"])
        rc, art = agent_job(s, mode)
        assert rc == 0, mode
        changed = {c["path"]: c["kind"] for c in json.loads((art / "changes.json").read_text())["changed"]}
        assert changed.get(expect[0]) == expect[1], (mode, changed)
        # The top-level .git is never exported: no git metadata leaves the agent job.
        assert not any(p.startswith(".git/") for p in changed)


def test_job_isolation_needs_the_commit_and_never_runs_containment(s, monkeypatch):
    monkeypatch.setattr(agent, "containment", lambda env: (_ for _ in ()).throw(AssertionError("contained")))
    with pytest.raises(AgentError, match="CI_COMMIT_SHA"):
        run_agent(mode="fix", workdir=s["work"], findings=s["findings"], out_dir=s["tmp"] / "a",
                  config_path=s["work"] / ".dawnfix.yml", env=s["env"], http=s["http"], claude_cmd=[str(s["claude"])],
                  isolation="job", base_commit="")


def test_the_namespace_mode_still_requires_containment(s, monkeypatch):
    monkeypatch.setattr(agent, "containment", lambda env: (_ for _ in ()).throw(AgentError("cannot contain")))
    with pytest.raises(AgentError, match="cannot contain"):
        run_agent(mode="fix", workdir=s["work"], findings=s["findings"], out_dir=s["tmp"] / "a",
                  config_path=s["work"] / ".dawnfix.yml", env=s["env"], http=s["http"], claude_cmd=[str(s["claude"])])


@pytest.mark.parametrize("env, ok", [
    ({"GITLAB_CI": "true"}, True), ({"BITBUCKET_BUILD_NUMBER": "3"}, True),
    ({"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "o/r"}, False), ({"CIRCLECI": "true"}, False), ({}, False)])
def test_isolation_job_only_where_each_job_is_a_fresh_container(s, env, ok, capsys, monkeypatch):
    seen = {}
    monkeypatch.setattr("dawnfix_core.run.cli.run_agent", lambda **kw: seen.update(kw) or 0)
    rc = run_main(["agent", "--mode", "fix", "--isolation", "job", "--dir", str(s["work"]), "--findings",
                   str(s["findings"]), "--out", str(s["tmp"] / "o")], env={**env, "DAWNFIX_AI_API_KEY": AI_KEY})
    if ok:
        assert rc == 0 and seen["isolation"] == "job"
    else:
        assert rc == 2 and "only for a CI that runs each stage in its own fresh container" in capsys.readouterr().err
        assert not seen


# --- publish: the only place a change is applied ---------------------------------------------
def test_publish_builds_the_patch_and_opens_a_draft_with_two_commits(s):
    rc, art = agent_job(s)
    rc, host = publish_job(s, art)
    assert rc == 0
    assert [c[0] for c in host.calls] == ["draft"]
    assert host.calls[0][1] == f"dawnfix/{FP}"
    log = sh(s["bare"], "log", "--format=%s", f"main..dawnfix/{FP}").splitlines()
    assert log == [f"fix: None user crashes name() (dawnfix {FP})", f"test: reproduce None user crashes name() (dawnfix {FP})"]
    assert sh(s["bare"], "diff", "--name-only", "main", f"dawnfix/{FP}").splitlines() == ["app/users.py", "tests/test_users.py"]


@pytest.mark.parametrize("mode, why", [
    ("ci", "touch CI config (.gitlab-ci.yml)"),
    ("ci-delete", "touch CI config (.gitlab-ci.yml)"),
    ("symlink", "symlink or submodule (app/link.py)"),
    ("binary", "binary file (app/blob.bin)"),
    ("gitdir", "touch a .git path (vendor/.git/config)"),
])
def test_publish_refuses_what_the_agent_job_exported(s, mode, why):
    rc, art = agent_job(s, mode)
    assert rc == 0
    with pytest.raises(Refused, match=__import__("re").escape(why)):
        publish_job(s, art)
    assert branches(s) == ""


def test_new_files_the_base_gitignore_ignores_are_left_out(s, capsys):
    rc, art = agent_job(s, "pycache")
    assert "app/__pycache__/users.cpython-312.pyc" in (art / "changes.json").read_text()
    rc, host = publish_job(s, art)
    assert rc == 0 and "left out" in capsys.readouterr().err
    assert sh(s["bare"], "diff", "--name-only", "main", f"dawnfix/{FP}").splitlines() == [
        "app/users.py", "tests/test_users.py"]


def test_a_credential_in_a_changed_file_is_never_pushed(s, capsys):
    rc, art = agent_job(s, "secret")
    assert rc == 0
    rc, host = publish_job(s, art)
    assert rc == 1 and host.calls == [] and branches(s) == ""
    assert "looks like a credential" in capsys.readouterr().err


def test_a_patch_in_the_artifact_is_refused_in_job_mode(s):
    """An agent job that writes a patch (as the namespace capture would) gets nothing applied."""
    rc, art = agent_job(s)
    (art / "agent.patch").write_bytes(b"diff --git a/.gitlab-ci.yml b/.gitlab-ci.yml\n")
    meta = json.loads((art / "meta.json").read_text())
    (art / "meta.json").write_text(json.dumps({**meta, "capture": "patch"}))
    with pytest.raises(PublishError, match="exported files of an agent job run with --isolation job"):
        publish_job(s, art)
    assert branches(s) == ""
    # With files declared, a planted patch is ignored: only the checked files are applied.
    (art / "meta.json").write_text(json.dumps(meta))
    rc, host = publish_job(s, art)
    assert rc == 0 and sh(s["bare"], "diff", "--name-only", "main", f"dawnfix/{FP}").splitlines() == [
        "app/users.py", "tests/test_users.py"]


@pytest.mark.parametrize("forge, why", [
    (lambda art: _changes(art, changed=[{"path": "../outside.py", "kind": "file"}]), "not a plain repo path"),
    (lambda art: _changes(art, changed=[{"path": "/etc/passwd", "kind": "file"}]), "not a plain repo path"),
    (lambda art: _changes(art, changed=[{"path": ".GIT/config", "kind": "file"}]), "touch a .git path"),
    (lambda art: _changes(art, changed=[{"path": ".github/workflows/x.yml", "kind": "file"}]), "touch a workflow"),
    (lambda art: _changes(art, changed=[{"path": ".circleci/config.yml", "kind": "file"}]), "touch CI config"),
    (lambda art: _changes(art, changed=[{"path": "bitbucket-pipelines.yml", "kind": "file"}]), "touch CI config"),
    (lambda art: _changes(art, deleted=[".gitlab-ci.yml"]), "touch CI config"),
    (lambda art: _changes(art, changed=[{"path": "app/x.py", "kind": "weird"}]), "unknown kind"),
    (lambda art: _plant_link(art, "app/users.py", "/etc/passwd"), "symlink or submodule (app/users.py)"),
    (lambda art: _plant_link(art, "app", "/etc"), "symlink or submodule (app/users.py)"),
    (lambda art: (art / "files" / "app" / "users.py").write_bytes(b"x\x00y"), "binary file (app/users.py)"),
])
def test_a_forged_artifact_is_refused(s, forge, why):
    rc, art = agent_job(s)
    forge(art)
    with pytest.raises(Refused, match=__import__("re").escape(why)):
        publish_job(s, art)
    assert branches(s) == ""


def test_a_forged_base_commit_is_refused(s):
    rc, art = agent_job(s)
    meta = json.loads((art / "meta.json").read_text())
    (art / "meta.json").write_text(json.dumps({**meta, "base_sha": "f" * 40}))
    with pytest.raises(PublishError, match="not the commit"):
        publish_job(s, art)
    os.remove(art / "changes.json")
    (art / "meta.json").write_text(json.dumps(meta))
    with pytest.raises(PublishError, match="no changes.json"):
        publish_job(s, art)


def test_a_process_left_behind_by_the_agent_cannot_bypass_publish(s, capsys):
    """Without a PID namespace, a setsid child may outlive the agent in its job. It can only
    change files the publish job then checks; nothing it writes is applied unchecked."""
    rc, art = agent_job(s, "setsid")
    assert rc == 0
    rc, host = publish_job(s, art)
    assert rc == 0
    files = sh(s["bare"], "diff", "--name-only", "main", f"dawnfix/{FP}").splitlines()
    assert files == ["app/users.py", "tests/test_users.py"]


def _changes(art, changed=None, deleted=None):
    doc = json.loads((art / "changes.json").read_text())
    if changed is not None:
        doc["changed"] = changed
    if deleted is not None:
        doc["deleted"] = deleted
    (art / "changes.json").write_text(json.dumps(doc))


def _plant_link(art, rel, target):
    p = art / "files" / rel
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    p.symlink_to(target)


# --- the agent job holds no CI credential and no git metadata ---------------------------------
@pytest.mark.parametrize("extra, why", [
    ({"CI_JOB_TOKEN": "glcbt-abcdefgh12345678"}, "CI_JOB_TOKEN"),
    ({"CI_REGISTRY_PASSWORD": "pw-abcdefgh"}, "CI_REGISTRY_PASSWORD"),
    ({"CI_DEPENDENCY_PROXY_PASSWORD": "pw-abcdefgh"}, "CI_DEPENDENCY_PROXY_PASSWORD"),
    ({"CI_REPOSITORY_URL": "https://gitlab-ci-token:secretvalue@gitlab.com/a/b.git"}, "CI_REPOSITORY_URL"),
    ({"GIT_ASKPASS": "/bin/askpass"}, "GIT_ASKPASS"),
])
def test_the_agent_job_refuses_to_start_with_a_ci_credential(s, extra, why, monkeypatch):
    monkeypatch.setattr(agent, "run_contained", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran")))
    with pytest.raises(AgentError, match=f"refuses to start: CI credentials are set .*{why}"):
        run_agent(mode="fix", workdir=s["work"], findings=s["findings"], out_dir=s["tmp"] / "a",
                  config_path=s["work"] / ".dawnfix.yml", env={**s["env"], **extra}, http=s["http"],
                  claude_cmd=[str(s["claude"])], isolation="job", base_commit=s["base"])


def test_the_agent_job_refuses_a_git_dir_or_a_credential_helper(s, monkeypatch):
    monkeypatch.setattr(agent, "run_contained", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran")))
    go = lambda env=s["env"]: run_agent(mode="fix", workdir=s["work"], findings=s["findings"], out_dir=s["tmp"] / "a",
                                        config_path=s["work"] / ".dawnfix.yml", env=env, http=s["http"],
                                        claude_cmd=[str(s["claude"])], isolation="job", base_commit=s["base"])
    (s["work"] / ".git").mkdir()
    with pytest.raises(AgentError, match="has a .git"):
        go()
    (s["work"] / ".git").rmdir()
    home = Path(s["env"]["HOME"])
    home.mkdir(parents=True, exist_ok=True)
    (home / ".gitconfig").write_text("[credential]\n\thelper = store\n")
    with pytest.raises(AgentError, match="configures git credentials"):
        go()
    (home / ".gitconfig").unlink()
    (home / ".git-credentials").write_text("https://u:p@gitlab.com\n")
    with pytest.raises(AgentError, match=".git-credentials exists"):
        go()
    assert agent.job_isolation_refusals({"HOME": str(s["tmp"] / "nohome")}, s["tmp"] / "nowhere", system_gitconfig=s["tmp"] / "none") == []


def test_the_branch_is_pushed_with_ci_skip(s):
    hook = s["bare"] / "hooks" / "pre-receive"
    rec = s["tmp"] / "push-options"
    hook.write_text(f'#!/bin/sh\ni=0\nwhile [ $i -lt "${{GIT_PUSH_OPTION_COUNT:-0}}" ]; do '
                    f'eval echo "\\$GIT_PUSH_OPTION_$i" >> "{rec}"; i=$((i+1)); done\ncat >/dev/null\n')
    hook.chmod(0o755)
    rc, art = agent_job(s)
    rc, host = publish_job(s, art)
    assert rc == 0 and rec.read_text().split() == ["ci.skip"]


# --- CI files a .gitlab-ci.yml includes locally ----------------------------------------------
def _with_includes(s, files):
    """Commit CI files with local includes to the origin, re-export the agent's tree."""
    for rel, text in files.items():
        p = s["origin"] / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    sh(s["origin"], "add", "-A")
    sh(s["origin"], "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "ci includes")
    sh(s["origin"], "push", "-q", str(s["bare"]), "main")
    s["base"] = sh(s["origin"], "rev-parse", "HEAD")
    export(s["origin"], s["work"])


INCLUDES = {
    ".gitlab-ci.yml": "include:\n  - local: build/jobs.yml\n  - local: '/deploy/*.yaml'\n  - remote: https://x.example/a.yml\n"
                      "test:\n  script: [!reference [.x, script]]\n",
    "build/jobs.yml": "include: build/nested/more.yml\njob: {script: [true]}\n",
    "build/nested/more.yml": "include:\n  local: 'shared/**.yml'\n",
    "deploy/prod.yaml": "deploy: {script: [true]}\n",
    "shared/a/b.yml": "x: 1\n",
    "app/settings.yml": "not: ci\n",
}


@pytest.mark.parametrize("target", ["build/jobs.yml", "build/nested/more.yml", "deploy/prod.yaml", "deploy/new.yaml",
                                    "shared/a/b.yml"])
def test_a_change_to_a_locally_included_ci_file_is_refused(s, target):
    _with_includes(s, INCLUDES)
    claude = s["claude"].read_text().replace(
        'out = w / ".dawnfix-run" / "out"',
        f'(w / "{target}").parent.mkdir(parents=True, exist_ok=True)\n'
        f'(w / "{target}").write_text("evil: {{script: [env]}}\\n")\nout = w / ".dawnfix-run" / "out"', 1)
    s["claude"].write_text(claude)
    rc, art = agent_job(s)
    assert rc == 0
    with pytest.raises(Refused, match=__import__("re").escape(f"touch CI config ({target}")):
        publish_job(s, art)
    assert branches(s) == ""


@pytest.mark.parametrize("path", ["deploy.gitlab-ci.yml", "x/y/z.gitlab-ci.yml", ".gitlab/ci/jobs.yml", "ci/a.yaml",
                                  "svc/ci/jobs.yml", ".bitbucket/x.yml", "bitbucket-pipelines.yml"])
def test_ci_config_names_are_refused_conservatively(path):
    from dawnfix_core.run.publish import CI_CONFIG
    assert CI_CONFIG.search(path), path


def test_a_non_ci_yaml_is_not_refused(s):
    _with_includes(s, INCLUDES)
    claude = s["claude"].read_text().replace(
        'out = w / ".dawnfix-run" / "out"',
        '(w / "app" / "settings.yml").write_text("now: changed\\n")\nout = w / ".dawnfix-run" / "out"', 1)
    s["claude"].write_text(claude)
    rc, art = agent_job(s)
    rc, host = publish_job(s, art)
    assert rc == 0  # an unclaimed change, dropped with a notice; the PR goes ahead


def test_the_custom_ci_config_path_and_its_includes(s):
    _with_includes(s, {"pipelines/main.yml": "include: {local: pipelines/part.yml}\n", "pipelines/part.yml": "a: 1\n"})
    from dawnfix_core.run.publish import refuse_ci_includes
    refuse_ci_includes(s["origin"], s["base"], ["app/users.py"], ("pipelines/main.yml",))
    for f in ("pipelines/main.yml", "pipelines/part.yml"):
        with pytest.raises(Refused, match="included by the CI configuration"):
            refuse_ci_includes(s["origin"], s["base"], [f], ("pipelines/main.yml",))
    # A config in another project or at a URL is nothing a change here can touch.
    refuse_ci_includes(s["origin"], s["base"], ["pipelines/part.yml"], ("ci.yml@grp/other",))


def test_the_agent_job_refuses_bitbucket_tokens_and_any_secret_named_variable(s):
    nowhere, none = s["tmp"] / "nowhere", s["tmp"] / "none"
    for name in ("BITBUCKET_STEP_OIDC_TOKEN", "BITBUCKET_ACCESS_TOKEN", "BITBUCKET_PIPELINES_TOKEN", "NPM_TOKEN",
                 "SENTRY_AUTH_TOKEN", "DB_PASSWORD", "STRIPE_SECRET", "OPENAI_API_KEY", "DEPLOY_PRIVATE_KEY",
                 "AWS_ACCESS_KEY_ID", "GOOGLE_CREDENTIALS"):
        why = agent.job_isolation_refusals({name: "v", "HOME": str(nowhere)}, nowhere, system_gitconfig=none)
        assert why and name in why[0], name
    # The AI key is the one secret the agent job is for; image variables like GPG_KEY are not secrets.
    for name in ("DAWNFIX_AI_API_KEY", "ANTHROPIC_API_KEY", "GPG_KEY", "BITBUCKET_COMMIT", "BITBUCKET_GIT_HTTP_ORIGIN"):
        assert agent.job_isolation_refusals({name: "https://bitbucket.org/a/b", "HOME": str(nowhere)}, nowhere, system_gitconfig=none) == [], name


def test_the_agent_job_refuses_every_ssh_credential_left(s, monkeypatch):
    home, pssh = s["tmp"] / "h", s["tmp"] / "pipelines-ssh"
    monkeypatch.setattr(agent, "PIPELINES_SSH_DIR", pssh)
    go = lambda env=None: agent.ssh_refusals({**(env or {})}, home, pssh)
    assert go() == []
    (home / ".ssh").mkdir(parents=True)
    (home / ".ssh" / "known_hosts").write_text("bitbucket.org ssh-ed25519 AAAA\n")
    (home / ".ssh" / "id_ed25519.pub").write_text("ssh-ed25519 AAAA")
    assert go() == []
    # SSH_AUTH_SOCK
    assert "SSH_AUTH_SOCK" in go({"SSH_AUTH_SOCK": "/tmp/agent.sock"})[0]
    # any non-empty file in the pipelines ssh directory, whatever its name
    pssh.mkdir()
    (pssh / "known").write_text("")
    (pssh / "..2026_11_27").mkdir()
    (pssh / "..2026_11_27" / "known_hosts").write_text("bitbucket.org ssh-rsa AAAA\n")
    assert go() == []
    (pssh / "anything").write_text("x")
    assert "holds files" in go()[0]
    (pssh / "anything").unlink()
    # BITBUCKET_SSH_KEY_FILE naming an existing file
    kf = s["tmp"] / "kf"
    kf.write_text("")
    assert "BITBUCKET_SSH_KEY_FILE" in go({"BITBUCKET_SSH_KEY_FILE": str(kf)})[0]
    assert go({"BITBUCKET_SSH_KEY_FILE": str(s["tmp"] / "gone")}) == []
    # a private-key header in any file under ~/.ssh, whatever its name
    (home / ".ssh" / "notes.txt").write_text("x\n" + "-----BEGIN OPENSSH " + "PRIVATE KEY-----\nb3Blbn\n")
    assert "holds a private key" in go()[0]
    (home / ".ssh" / "notes.txt").write_text("-----BEGIN RSA " + "PRIVATE KEY-----\n")
    assert "holds a private key" in go()[0]
    (home / ".ssh" / "notes.txt").unlink()
    # an IdentityFile named in ~/.ssh/config that exists anywhere
    ident = s["tmp"] / "deploy-key"
    ident.write_text("not a key header")
    (home / ".ssh" / "config").write_text(f"Host bitbucket.org\n  IdentityFile {ident}\n")
    assert "an IdentityFile" in go()[0]
    ident.unlink()
    assert go() == []
    # and through the agent job's own check
    why = agent.job_isolation_refusals({"HOME": str(home), "SSH_AUTH_SOCK": "/x"}, s["tmp"] / "nowhere",
                                       system_gitconfig=s["tmp"] / "none")
    assert any("SSH_AUTH_SOCK" in w for w in why)


def test_the_sandbox_probe_says_whether_bwrap_can_start():
    assert "not installed" in agent.sandbox_probe(which=lambda n: None)
    assert "can create namespaces" in agent.sandbox_probe(which=lambda n: "/usr/bin/bwrap", probe=lambda c: True)
    line = agent.sandbox_probe(which=lambda n: "/usr/bin/bwrap", probe=lambda c: False)
    assert "cannot create namespaces" in line and "Bash tool is refused" in line


def test_bitbucket_needs_the_network_sandbox_in_fix_mode():
    settings = agent.tools("fix", "python3 -m unittest")[2]
    ok = lambda cmd: True
    assert agent.network_sandbox_refusal("fix", settings, which=lambda n: "/usr/bin/bwrap", probe=ok) == ""
    assert agent.network_sandbox_refusal("diagnose", {}, which=lambda n: None) == ""  # no command runs
    assert "not installed" in agent.network_sandbox_refusal("fix", settings, which=lambda n: None)
    seen = []
    why = agent.network_sandbox_refusal("fix", settings, which=lambda n: "/usr/bin/bwrap",
                                        probe=lambda cmd: seen.append(cmd) or False)
    assert "cannot create user and network namespaces" in why and "--unshare-net" in seen[0]
    import copy
    loose = copy.deepcopy(settings)
    loose["sandbox"]["failIfUnavailable"] = False
    assert "not required" in agent.network_sandbox_refusal("fix", loose, which=lambda n: "/b", probe=ok)
    local = copy.deepcopy(settings)
    local["sandbox"]["network"]["allowedDomains"].append("localhost")
    assert "local host" in agent.network_sandbox_refusal("fix", local, which=lambda n: "/b", probe=ok)


@pytest.mark.parametrize("mode, line", [("fix", "required on Bitbucket Pipelines and able to start"),
                                        ("diagnose", "not needed in diagnose mode")])
def test_bitbucket_sandbox_line_says_what_the_mode_checked(s, mode, line, capsys, monkeypatch):
    monkeypatch.setattr(agent, "network_sandbox_refusal", lambda *a, **k: "")
    monkeypatch.setattr(agent, "job_isolation_refusals", lambda *a, **k: ["stop here"])
    with pytest.raises(AgentError):
        run_agent(mode=mode, workdir=s["work"], findings=s["findings"], out_dir=s["tmp"] / "o",
                  config_path=s["work"] / ".dawnfix.yml", env={**s["env"]}, http=s["http"], isolation="job",
                  require_network_sandbox=True)
    assert line in capsys.readouterr().err
