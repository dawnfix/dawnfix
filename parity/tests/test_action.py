"""Run the composite action's shell step with a fake `parity` on PATH."""
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def step(name):
    doc = yaml.safe_load((ROOT / "action.yml").read_text())
    return next(s for s in doc["runs"]["steps"] if s.get("id") == name)


@pytest.mark.parametrize("hashes, fail_on, code", [("false", "", 0), ("true", "type_mismatch", 1)])
def test_check_step(tmp_path, hashes, fail_on, code):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "parity"
    fake.write_text(f'#!/bin/bash\nprintf "%s\\n" "$@" > "{tmp_path}/args"\nexit {code}\n')
    fake.chmod(0o755)
    out, summary = tmp_path / "out", tmp_path / "summary"
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "GITHUB_OUTPUT": str(out),
           "GITHUB_STEP_SUMMARY": str(summary), "INPUT_LEFT": "dev", "INPUT_RIGHT": "prod",
           "INPUT_CONFIG": ".parity.yml", "INPUT_HASHES": hashes, "INPUT_FAIL_ON": fail_on}
    r = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step("check")["run"]],
                       env=env, capture_output=True, text=True)
    assert r.returncode == code, r.stderr
    assert out.read_text() == f"exit-code={code}\n"
    args = (tmp_path / "args").read_text().split("\n")
    assert args[:8] == ["-c", ".parity.yml", "check", "--left", "dev", "--right", "prod", "--summary"]
    assert ("--compare-hashes" in args) == (hashes == "true")
    assert ("--fail-on" in args) == bool(fail_on)


def test_workflow_uses_oidc():
    wf = yaml.safe_load((ROOT / "examples" / "workflow.yml").read_text())
    assert wf["permissions"] == {"id-token": "write", "contents": "read"}
    steps = wf["jobs"]["parity"]["steps"]
    assert any(s.get("uses", "").startswith("aws-actions/configure-aws-credentials") for s in steps)
    assert not any("aws-access-key-id" in (s.get("with") or {}) for s in steps)
