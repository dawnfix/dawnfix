"""dawnfix run agent: Claude Code headless with the workflow's restrictions, a minimal
environment (the AI key and nothing else secret), and the capture of its changes with a .git
it never saw. A fake `claude` stands in for the real one."""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from dawnfix_core.run import agent
from dawnfix_core.run.agent import AgentError, run_agent

from .run_fakes import AI_KEY, FakeHttp

FP = "1997f26556fdd1c5"
CONFIG = ("version: 1\nautonomy: draft-pr\nsources: [{aws: {region: us-east-1, alarms: true}}]\n"
          "limits: {fix_prs_per_day: 2, max_turns: 30}\ntest: {command: npm test}\n")

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, sys, pathlib
rec = {"argv": sys.argv[1:], "env": dict(os.environ), "prompt": sys.stdin.read(), "cwd": os.getcwd()}
pathlib.Path(os.environ["FAKE_RECORD"]).write_text(json.dumps(rec))
mode = os.environ.get("FAKE_MODE", "fix")
if mode == "fail":
    sys.exit(3)
if mode == "bg":
    # A background process that keeps writing into the tree after the agent exits.
    import subprocess
    pathlib.Path("src/bg.js").write_text("// 0\n")
    p = subprocess.Popen(["sh", "-c", "i=0; while true; do i=$((i+1)); echo \"// $i\" >> src/bg.js; sleep 0.02; done"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pathlib.Path(os.environ["FAKE_MARKER"] + ".pid").write_text(str(p.pid))
if mode == "setsid":
    # Escape the process group: a new session that keeps writing after the agent exits.
    import subprocess
    pathlib.Path("src/esc.js").write_text("// 0\n")
    subprocess.Popen(["setsid", "sh", "-c", f"echo $$ > '{os.environ['FAKE_MARKER']}.pid'; sleep 0.3; "
                      "while true; do echo x >> src/esc.js; sleep 0.02; done"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    import time; time.sleep(0.2)
if mode == "attrs":
    w = pathlib.Path(".")
    marker = os.environ["FAKE_MARKER"]
    (w / ".gitattributes").write_text("* filter=evil diff=evil\n")
    with open(w / ".git" / "config", "a") as f:
        f.write(f"[filter \"evil\"]\n\tclean = sh -c \"touch '{marker}'; cat\"\n\tsmudge = sh -c \"touch '{marker}'; cat\"\n"
                f"[diff \"evil\"]\n\ttextconv = sh -c \"touch '{marker}'; cat\"\n")
    hook = w / ".git" / "hooks" / "post-checkout"
    hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n"); hook.chmod(0o755)
    (w / "src" / "users.js").write_text("export const name = (u) => u?.name ?? '';\n")
w = pathlib.Path(".")
if mode == "fix":
    (w / "tests" / "users.test.js").write_text("test('null user', () => expect(name(null)).toBe(''));\n")
    (w / "src" / "users.js").write_text("export const name = (u) => u?.name ?? '';\n")
    # Planted for the capture: a hook and an fsmonitor in its own .git, which must never run.
    marker = os.environ["FAKE_MARKER"]
    hook = w / ".git" / "hooks" / "pre-commit"
    hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n"); hook.chmod(0o755)
    with open(w / ".git" / "config", "a") as f:
        f.write(f"[core]\n\tfsmonitor = touch '{marker}'; echo\n")
if mode == "tamper":
    for snap in pathlib.Path(os.environ["FAKE_SNAPS"]).glob("*/git"):
        os.chmod(snap / "config", 0o644)
        with open(snap / "config", "a") as f:
            f.write("[filter \"evil\"]\n\tclean = touch x\n")
out = w / ".dawnfix-run" / "out"
(out / "result.json").write_text(json.dumps({"schema": "dawnfix.result/1", "results": [
    {"fingerprint": "1997f26556fdd1c5", "action": "pr", "title": "t", "test_files": ["tests/users.test.js"],
     "fix_files": ["src/users.js"]}]}))
(out / "1997f26556fdd1c5.md").write_text("## Cause\nx\n")
(out / "evil.md").symlink_to("/etc/passwd")
print("done")
'''


def sh(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}).stdout


@pytest.fixture
def setup(tmp_path):
    work = tmp_path / "w"
    (work / "src").mkdir(parents=True)
    (work / "tests").mkdir()
    (work / "src" / "users.js").write_text("export const name = (u) => u.name;\n")
    (work / ".dawnfix.yml").write_text(CONFIG)
    sh(work, "init", "-q", "-b", "main")
    sh(work, "add", "-A")
    sh(work, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    claude = tmp_path / "bin" / "claude"
    claude.parent.mkdir()
    claude.write_text(FAKE_CLAUDE)
    claude.chmod(0o755)
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps({"findings": [{"fingerprint": FP}]}))
    prompt = "<!-- dawnfix:ci-prompt fix -->\n# Dawnfix CI: fix\nDo it.\n"
    http = FakeHttp({("GET", "https://raw.githubusercontent.com/dawnfix/dawnfix/"): (200, prompt)})
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home"), "DAWNFIX_AI_API_KEY": AI_KEY,
           "FAKE_RECORD": str(tmp_path / "record.json"), "FAKE_MARKER": str(tmp_path / "marker"),
           "FAKE_SNAPS": str(tmp_path / "snaps"), "CI_JOB_TOKEN": "ambient-job-token", "CI": "true",
           "DAWNFIX_ALLOW_UNCONTAINED": "1"}
    (tmp_path / "snaps").mkdir()
    if sys.platform.startswith("linux"):
        try:
            agent.containment(env)
        except AgentError:
            pytest.skip("this Linux host cannot contain processes (no PID namespace): the stage fails closed here")
    return dict(work=work, claude=claude, findings=findings, http=http, env=env, tmp=tmp_path)


def go(s, mode="fix", fake="fix", **kw):
    env = {**s["env"], "FAKE_MODE": fake}
    return run_agent(mode=mode, workdir=s["work"], findings=s["findings"], out_dir=s["tmp"] / "out",
                     config_path=s["work"] / ".dawnfix.yml", env=env, http=s["http"], claude_cmd=[str(s["claude"])],
                     pass_env=["FAKE_RECORD", "FAKE_MARKER", "FAKE_MODE", "FAKE_SNAPS"],
                     snapshot_dir=s["tmp"] / "snaps", **kw)


def test_fix_runs_claude_with_the_workflow_restrictions_and_captures_a_patch(setup):
    s = setup
    assert go(s) == 0
    rec = json.loads((s["tmp"] / "record.json").read_text())
    argv = rec["argv"]
    assert argv[0] == "-p" and argv[argv.index("--model") + 1] == "sonnet"
    assert argv[argv.index("--max-turns") + 1] == "30"
    assert argv[argv.index("--allowedTools") + 1] == "Read,Edit,Write,Glob,Grep,Bash(npm test:*)"
    assert "Bash(git:*)" in argv[argv.index("--disallowedTools") + 1]
    assert argv[argv.index("--setting-sources") + 1] == "user" and "--strict-mcp-config" in argv
    assert argv[argv.index("--output-format") + 1] == "json"
    # The child had the key under the name Claude Code reads, and no CI token of any kind.
    env = rec["env"]
    assert env["ANTHROPIC_API_KEY"] == AI_KEY and "DAWNFIX_AI_API_KEY" not in env
    assert "CI_JOB_TOKEN" not in env and env["DAWNFIX_AUTONOMY"] == "draft-pr"
    assert not any(k in env for k in ("GITHUB_TOKEN", "DAWNFIX_HOST_TOKEN", "DAWNFIX_ENTERPRISE_KEY"))
    # The prompt: the instructions, then this run, as the workflow writes it.
    assert rec["prompt"].startswith("<!-- dawnfix:ci-prompt fix -->")
    assert "Findings file: .dawnfix-run/findings.json" in rec["prompt"]
    assert "Autonomy: draft-pr. Draft PRs left today: 2." in rec["prompt"] and "`npm test`" in rec["prompt"]
    assert s["http"].calls[0]["url"].endswith("/prompts/ci/fix.md")
    out = s["tmp"] / "out"
    patch = (out / "agent.patch").read_text()
    assert "+++ b/tests/users.test.js" in patch and "+++ b/src/users.js" in patch and ".dawnfix-run" not in patch
    assert sorted(p.name for p in (out / "run").iterdir()) == [f"{FP}.md", "result.json"]  # no symlink
    meta = json.loads((out / "meta.json").read_text())
    assert meta["mode"] == "fix" and meta["base_sha"] == sh(s["work"], "rev-parse", "HEAD").strip()
    assert not (s["tmp"] / "marker").exists(), "a hook or fsmonitor planted by the agent ran"
    assert list((s["tmp"] / "snaps").iterdir()) == []


def test_diagnose_has_no_shell_no_patch(setup):
    s = setup
    s["http"].answers = [(("GET", "https://raw.githubusercontent.com/"), (200, "<!-- dawnfix:ci-prompt diagnose -->\nx\n"))]
    assert go(s, mode="diagnose", fake="diagnose") == 0
    argv = json.loads((s["tmp"] / "record.json").read_text())["argv"]
    assert argv[argv.index("--allowedTools") + 1] == "Read,Glob,Grep,Write"
    assert argv[argv.index("--disallowedTools") + 1].startswith("Bash,")
    assert not (s["tmp"] / "out" / "agent.patch").exists()
    assert (s["tmp"] / "out" / "run" / "result.json").exists()


def test_settings_deny_git_outside_and_ci_config(setup):
    _, _, settings = agent.tools("fix", "npm test")
    deny = settings["permissions"]["deny"]
    for rule in ("Edit(./.git/**)", "Write(~/**)", "Edit(./.gitlab-ci.yml)", "Edit(./bitbucket-pipelines.yml)",
                 "Edit(./.circleci/**)", "Edit(./.github/**)"):
        assert rule in deny
    assert settings["sandbox"]["failIfUnavailable"] is True and settings["sandbox"]["network"]["strictAllowlist"] is True


def test_a_checkout_under_home_keeps_its_edits_allowed(setup, capsys):
    s = setup
    s["env"]["HOME"] = str(s["tmp"])
    assert go(s) == 0
    assert "Edit(~/**)" in capsys.readouterr().err


def test_a_tampered_snapshot_captures_nothing(setup, capsys):
    assert go(setup, fake="tamper") == 1
    assert "snapshot .git changed" in capsys.readouterr().err
    assert not (setup["tmp"] / "out" / "agent.patch").exists()


def test_a_failed_agent_captures_nothing(setup, capsys):
    assert go(setup, fake="fail") == 1
    assert "exited 3" in capsys.readouterr().err and not (setup["tmp"] / "out").exists()
    assert list((setup["tmp"] / "snaps").iterdir()) == []


@pytest.mark.parametrize("status, text, msg", [
    (404, "", "has no prompts/ci/fix.md"),
    (200, "# not the prompt\n", "is not the Dawnfix fix prompt"),
    (500, "", "could not load"),
])
def test_instructions_must_be_the_pinned_prompt(setup, status, text, msg):
    s = setup
    s["http"].answers = [(("GET", "https://raw.githubusercontent.com/"), (status, text))]
    with pytest.raises(AgentError, match=msg):
        go(s)
    assert not (s["tmp"] / "record.json").exists()


def test_prompt_ref_and_pass_env(setup):
    from dawnfix_core import __version__
    assert agent.prompt_ref({}) == f"v{__version__}"
    assert agent.prompt_ref({"DAWNFIX_CORE_REF": "abc123"}) == "abc123"
    with pytest.raises(AgentError):
        agent.prompt_ref({"DAWNFIX_CORE_REF": "v1; rm -rf /"})
    with pytest.raises(AgentError, match="secrets never reach the agent"):
        agent.child_env({}, "k", "diagnose", pass_env=["MY_TOKEN"])


def test_out_inside_the_checkout_is_refused(setup):
    s = setup
    with pytest.raises(AgentError, match="outside the checkout"):
        run_agent(mode="fix", workdir=s["work"], findings=s["findings"], out_dir=s["work"] / "out",
                  config_path=s["work"] / ".dawnfix.yml", env=s["env"], http=s["http"], claude_cmd=[str(s["claude"])])


def test_a_background_process_the_agent_left_is_killed_before_the_capture(setup):
    s = setup
    assert go(s, fake="bg") == 0
    pid = int((s["tmp"] / "marker.pid").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    size = (s["work"] / "src" / "bg.js").stat().st_size
    import time
    time.sleep(0.3)
    assert (s["work"] / "src" / "bg.js").stat().st_size == size, "something still writes into the tree"
    patch = (s["tmp"] / "out" / "agent.patch").read_text()
    assert "+++ b/src/bg.js" in patch


def test_a_planted_attributes_filter_and_hooks_never_run(setup):
    s = setup
    assert go(s, fake="attrs") == 0
    assert not (s["tmp"] / "marker").exists(), "a filter, diff driver or hook planted by the agent ran"
    patch = (s["tmp"] / "out" / "agent.patch").read_text()
    assert "+++ b/src/users.js" in patch and "+++ b/.gitattributes" in patch


@pytest.mark.parametrize("plant, why", [
    ("symlink", "symlink or submodule (src/link.js)"),
    ("binary", "include a binary file (src/blob.bin)"),
    ("ci", "touch CI config (.gitlab-ci.yml)"),
    ("workflow", "touch a workflow (.github/workflows/x.yml)"),
    ("nested", "symlink or submodule (vendor/x)"),
])
def test_the_capture_copies_only_regular_text_files(setup, capsys, plant, why):
    s = setup
    w = s["work"]
    if plant == "symlink":
        (w / "src" / "link.js").symlink_to("/etc/passwd")
    elif plant == "binary":
        (w / "src" / "blob.bin").write_bytes(b"\0\1\2")
    elif plant == "ci":
        (w / ".gitlab-ci.yml").write_text("x: 1\n")
    elif plant == "workflow":
        (w / ".github" / "workflows").mkdir(parents=True)
        (w / ".github" / "workflows" / "x.yml").write_text("on: push\n")
    else:
        (w / "vendor" / "x").mkdir(parents=True)
        sh(w / "vendor" / "x", "init", "-q")
        (w / "vendor" / "x" / "f").write_text("x\n")
    assert go(s) == 1
    assert why in capsys.readouterr().err
    assert not (s["tmp"] / "out").exists()


def test_the_artifact_carries_secret_hashes_never_values(setup):
    s = setup
    (s["findings"].parent / "secret-hashes.json").write_text(json.dumps({"hashes": [{"len": 12, "sha256": "a" * 64}]}))
    assert go(s) == 0
    text = (s["tmp"] / "out" / "secret-hashes.json").read_text()
    assert AI_KEY not in text and "ambient-job-token" not in text
    import hashlib
    hashes = {e["sha256"] for e in json.loads(text)["hashes"]}
    assert hashlib.sha256(AI_KEY.encode()).hexdigest() in hashes
    assert hashlib.sha256(b"ambient-job-token").hexdigest() in hashes and "a" * 64 in hashes


def test_env_dump_and_proc_are_denied():
    for mode in ("fix", "diagnose"):
        deny = agent.tools(mode, "npm test")[2]["permissions"]["deny"]
        assert "Read(//proc/**)" in deny and "Read(//sys/**)" in deny
    deny = agent.tools("fix", "npm test")[2]["permissions"]["deny"]
    for rule in ("Bash(env:*)", "Bash(printenv:*)", "Bash(export:*)", "Bash(set:*)", "Bash(declare:*)"):
        assert rule in deny


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="PID namespaces are Linux only")
def test_a_setsid_child_is_dead_before_the_capture(setup):
    s = setup
    s["env"].pop("DAWNFIX_ALLOW_UNCONTAINED")
    assert go(s, fake="setsid") == 0
    import time
    time.sleep(0.5)
    pid = int((s["tmp"] / "marker.pid").read_text().strip())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)  # (inside the namespace it had another number; either way, nothing runs)
    size = (s["work"] / "src" / "esc.js").stat().st_size
    time.sleep(0.4)
    assert (s["work"] / "src" / "esc.js").stat().st_size == size


def test_no_containment_fails_closed(tmp_path, capsys):
    with pytest.raises(AgentError, match="refusing to run the agent stage"):
        agent.containment({}, platform="linux", which=lambda n: None)
    with pytest.raises(AgentError, match="refusing to run the agent stage"):
        agent.containment({}, platform="linux", which=lambda n: f"/usr/bin/{n}", probe=lambda c: False)
    with pytest.raises(AgentError, match="DAWNFIX_ALLOW_UNCONTAINED=1"):
        agent.containment({}, platform="darwin")
    assert agent.containment({"DAWNFIX_ALLOW_UNCONTAINED": "1"}, platform="darwin")["kind"] == "process-group"
    assert "local development only" in capsys.readouterr().err
    c = agent.containment({}, platform="linux", which=lambda n: f"/usr/bin/{n}", probe=lambda c: True)
    assert c["kind"] == "pid-namespace" and c["prefix"][:5] == ["/usr/bin/unshare", "--pid", "--fork", "--kill-child", "--mount-proc"]
    c = agent.containment({}, platform="linux", which=lambda n: f"/usr/bin/{n}" if n != "unshare" and n != "bwrap" else None,
                          probe=lambda c: True)
    assert c["kind"] == "cgroup" and c["kill"][-2] == "--signal=SIGKILL"
    # The stage itself refuses before it snapshots, loads a prompt or runs anything.
    monkeypatch_env = {"DAWNFIX_AI_API_KEY": AI_KEY}
    orig = agent.containment
    try:
        agent.containment = lambda env: orig(env, platform="linux", which=lambda n: None)
        (tmp_path / "w").mkdir()
        (tmp_path / "w" / ".dawnfix.yml").write_text(CONFIG)
        with pytest.raises(AgentError, match="refusing to run the agent stage"):
            run_agent(mode="fix", workdir=tmp_path / "w", findings=tmp_path / "f.json", out_dir=tmp_path / "out",
                      config_path=tmp_path / "w" / ".dawnfix.yml", env=monkeypatch_env, http=FakeHttp(),
                      claude_cmd=["/bin/false"])
    finally:
        agent.containment = orig
    assert not (tmp_path / "out").exists()


def test_a_file_swapped_for_a_symlink_between_listing_and_reading_is_refused(setup, monkeypatch, capsys):
    s = setup
    secret = s["tmp"] / "runner-secret"
    secret.write_text("do not capture me\n")

    def swap(rel):
        if rel == "src/users.js":
            f = s["work"] / rel
            f.unlink()
            f.symlink_to(secret)

    monkeypatch.setattr(agent, "_before_read", swap)
    assert go(s) == 1
    assert "symlink or submodule (src/users.js)" in capsys.readouterr().err
    assert not (s["tmp"] / "out").exists()


def test_read_nofollow_refuses_symlinked_parents_and_big_files(tmp_path):
    from dawnfix_core.run.publish import Refused
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "f.js").write_text("x\n")
    (tmp_path / "link").symlink_to(tmp_path / "real")
    assert agent.read_nofollow(tmp_path, "real/f.js") == (b"x\n", False)
    with pytest.raises(Refused, match="symlink"):
        agent.read_nofollow(tmp_path, "link/f.js")
    (tmp_path / "big.txt").write_bytes(b"a" * 2048)
    with pytest.raises(Refused, match="over"):
        agent.read_nofollow(tmp_path, "big.txt", cap=1024)


def test_the_log_shows_turns_tokens_and_cost_from_the_json_result():
    out = json.dumps({"type": "result", "subtype": "success", "is_error": False, "num_turns": 12, "duration_ms": 95000,
                      "total_cost_usd": 0.4321, "result": "Opened a fix.\nDone.",
                      "usage": {"input_tokens": 100, "output_tokens": 2000, "cache_read_input_tokens": 30000,
                                "cache_creation_input_tokens": 4000}})
    lines = agent.agent_log("warming up\n" + out)
    assert lines[0] == "result: success, 12 turns, 95s"
    assert lines[1] == "tokens: input 100, output 2000, cache read 30000, cache write 4000; cost $0.4321"
    assert lines[2:] == ["Opened a fix.", "Done."]
    assert agent.agent_log("plain\ntext") == ["plain", "text"]
