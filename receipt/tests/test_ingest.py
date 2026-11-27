"""What leaves the customer's CI: the counts-only dawnfix.receipt/1 document, and the IAM policy."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dawnfix_receipt import cli
from dawnfix_receipt import ingest
from dawnfix_receipt.guard import READ_ONLY_OPERATIONS, iam_actions
from tests.test_receipt import A, B, FINAL_NOW, SHA, args, ce, day_result, expected_req, series  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema" / "receipt-ingest.schema.json").read_text())
# Everything a receipt run knows that could identify the customer or their resources.
SECRETS = ["abc1234", SHA, "NatGateway", "USE1", "t3.medium", "BoxUsage", "TimedStorage", "payments", "team",
           "o/r", "123456789012"]


def validate(doc):
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(doc, SCHEMA)


def test_final_receipt_ingest_is_counts_only(ce, tmp_path):
    c, st = ce
    st.add_response("get_cost_and_usage", {"ResultsByTime": series(B, A)}, expected_req("2026-10-17", "2026-10-24"))
    tag_days = [day_result(d, {("team$payments",): 5.0}) for d in B] + [day_result(d, {("team$payments",): 44.0}) for d in A]
    st.add_response("get_cost_and_usage", {"ResultsByTime": tag_days},
                    expected_req("2026-10-17", "2026-10-24", [{"Type": "TAG", "Key": "team"}]))
    st.activate()
    out = tmp_path / "receipt-ingest.json"
    assert cli.run(args("--tag-key", "team", "--ingest-out", str(out), "--repo", "o/r"), ce=c, now=FINAL_NOW) == 0
    text = out.read_text()
    doc = json.loads(text)
    validate(doc)
    assert doc == {"schema": "dawnfix.receipt/1", "generated_at": "2026-10-25T09:00:00Z", "deploys": [{
        "deploy_id": ingest.deploy_id(SHA), "deployed_on": "2026-10-20", "window_days": 3, "after_days": 3,
        "final": True, "material": True, "delta_cents_per_day_bucket": 2000, "top_driver": "ec2_other"}]}
    for s in SECRETS:
        assert s.lower() not in text.lower(), s
    # no totals: before/after $/day would give away the size of the bill
    assert not re.search(r"before|after_usd|13\.2|53\.2", text)


def test_provisional_then_final_replaces_the_same_deploy(ce, tmp_path):
    c, st = ce
    early = datetime(2026, 10, 23, 6, tzinfo=timezone.utc)
    st.add_response("get_cost_and_usage", {"ResultsByTime": series(B, A[:1])}, expected_req("2026-10-17", "2026-10-22"))
    st.add_response("get_cost_and_usage", {"ResultsByTime": series(B, A)}, expected_req("2026-10-17", "2026-10-24"))
    st.activate()
    out = tmp_path / "i.json"
    assert cli.run(args("--ingest-out", str(out)), ce=c, now=early) == 0
    first = json.loads(out.read_text())["deploys"]
    assert len(first) == 1 and first[0]["final"] is False and first[0]["after_days"] == 1
    assert cli.run(args("--ingest-out", str(out)), ce=c, now=FINAL_NOW) == 0
    doc = json.loads(out.read_text())
    validate(doc)
    assert len(doc["deploys"]) == 1 and doc["deploys"][0]["final"] is True


def test_waiting_deploy_and_a_second_deploy_share_one_document(ce, tmp_path):
    c, st = ce
    st.activate()
    out = tmp_path / "i.json"
    waiting = datetime(2026, 10, 21, 6, tzinfo=timezone.utc)
    assert cli.run(args("--ingest-out", str(out)), ce=c, now=waiting) == 0
    other = cli.parser().parse_args(["--deploy-sha", "f" * 40, "--deployed-at", "2026-10-20T20:00:00Z",
                                     "--cache-dir", "", "--ingest-out", str(out)])
    assert cli.run(other, ce=c, now=waiting) == 0
    doc = json.loads(out.read_text())
    validate(doc)
    assert [d["after_days"] for d in doc["deploys"]] == [0, 0]
    assert all(d["delta_cents_per_day_bucket"] == 0 and d["top_driver"] == "none" for d in doc["deploys"])
    assert len({d["deploy_id"] for d in doc["deploys"]}) == 2


def test_bucket_grid():
    assert [ingest.bucket(x) for x in (0, 0.99, 1.0, 1.99, 4.99, 5, 40.07, -40.07, -0.5, 123456.0)] == \
        [0, 0, 100, 100, 200, 500, 2000, -2000, 0, 10_000_000]
    signed = set(SCHEMA["$defs"]["deploy"]["properties"]["delta_cents_per_day_bucket"]["enum"])
    assert {ingest.bucket(x / 7) for x in range(-10**6, 10**6, 997)} <= signed


def test_driver_enum_is_closed():
    assert ingest.driver("EC2 - Other") == "ec2_other"
    assert ingest.driver("Amazon Relational Database Service") == "rds"
    assert ingest.driver("Some Customer Thing; DROP TABLE") == "other"
    assert set(SCHEMA["$defs"]["deploy"]["properties"]["top_driver"]["enum"]) == set(ingest.DRIVER_ENUM)


def test_iam_policy_is_exactly_the_allowlist():
    doc = json.loads((ROOT / "iam" / "receipt-ce-read-policy.json").read_text())
    acts = {a for st in doc["Statement"] for a in st["Action"]}
    assert acts == iam_actions() == {"ce:GetCostAndUsage"}
    assert set(READ_ONLY_OPERATIONS) == {"ce"}
    trust = json.loads((ROOT / "iam" / "github-oidc-trust-policy.json").read_text())
    sub = trust["Statement"][0]["Condition"]["StringEquals"]["token.actions.githubusercontent.com:sub"]
    assert sub == "repo:OWNER/REPO:environment:dawnfix-receipt"


def test_guard_refuses_other_services():
    import boto3

    from dawnfix_receipt.guard import ReadOnlyViolation, make_client

    s = boto3.session.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name="us-east-1")
    with pytest.raises(ReadOnlyViolation):
        make_client(s, "s3")


def test_licence_is_fsl_at_the_repo_root():
    assert not (ROOT / "LICENSE").exists()
    assert "Functional Source License" in (ROOT.parent / "LICENSE").read_text()
    assert 'license = "FSL-1.1-ALv2"' in (ROOT / "pyproject.toml").read_text()
