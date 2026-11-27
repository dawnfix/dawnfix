"""The IAM policy Leastpriv needs is exactly its allowlist; licence, brand and pitch."""
import json
from pathlib import Path

import boto3
import pytest

from dawnfix_leastpriv import constants
from dawnfix_leastpriv.guard import ReadOnlyViolation, iam_actions, make_client
from tests.test_leastpriv import _env, clients, run  # noqa: F401 (fixtures)

ROOT = Path(__file__).resolve().parent.parent


def test_iam_policy_is_exactly_the_allowlist():
    doc = json.loads((ROOT / "iam" / "leastpriv-read-only-policy.json").read_text())
    acts = {a for st in doc["Statement"] for a in st["Action"]}
    assert acts == iam_actions()
    for a in acts:
        assert a.split(":")[1].startswith(("Get", "List", "GenerateServiceLastAccessedDetails")), a
    assert "access-analyzer:GenerateFindingRecommendation" not in acts


def test_guard_refuses_other_services():
    s = boto3.session.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name="us-east-1")
    with pytest.raises(ReadOnlyViolation):
        make_client(s, "sts", "us-east-1")


def test_report_carries_the_pitch_and_default_out_dir(clients, tmp_path):
    _, rep, _ = run(clients, tmp_path)
    assert rep["pitch"] == {"line": constants.PITCH_LINE, "url": constants.PITCH_URL}
    for gone in ("Solo", "paid", "plans", "$"):
        assert gone not in constants.PITCH_LINE
    from dawnfix_leastpriv import cli

    assert cli.parser().parse_args(["role", "r"]).out == "leastpriv-out" == constants.OUT_DIR


def test_licence_is_fsl_and_the_old_name_is_gone():
    assert not (ROOT / "LICENSE").exists()
    assert "Functional Source License" in (ROOT.parent / "LICENSE").read_text()
    assert 'license = "FSL-1.1-ALv2"' in (ROOT / "pyproject.toml").read_text()
    old = "iam" + "trim"
    for f in ROOT.rglob("*"):
        if f.is_file() and not {".venv", "__pycache__", ".pytest_cache"} & set(f.parts) and ".egg-info" not in str(f):
            text = f.read_text(errors="ignore").lower()
            hits = text.count(old)
            if f.name == "README.md":
                assert hits <= 1, f  # the one "formerly ..." line
            else:
                assert hits == 0, f
