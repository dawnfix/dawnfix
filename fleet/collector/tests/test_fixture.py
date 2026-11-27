"""The cross-language contract: fixtures/summary.json is what this collector writes for a
stubbed two-account client, and worker/test/fleet POSTs exactly that file.

    make fixture      # rewrite it after a deliberate change
"""
import json
import os
from datetime import timedelta

from dawnfix_fleet.collect import collect
from dawnfix_fleet.config import parse

from .conftest import (ACCOUNT, EXTERNAL_ID, FIXTURE_PATH, NOW, ROLE, SLUG, FakeSession, alarm, assume_ok,
                       ce_days, cert_detail, schema_validate)

STAGING = "444455556666"


def stubbed_collection(tmp_path):
    clients = parse({"version": 1, "clients": {SLUG: {"accounts": [
        {"provider": "aws", "env": "prod", "account_id": ACCOUNT, "role_arn": ROLE,
         "external_id_env": "FLEET_EXTERNAL_ID", "regions": ["us-east-1", "eu-west-1"]},
        {"provider": "aws", "env": "staging", "account_id": STAGING,
         "role_arn": f"arn:aws:iam::{STAGING}:role/fleet-read", "external_id_env": "FLEET_EXTERNAL_ID",
         "regions": ["eu-west-1"], "checks": ["alarms", "certs"]},
    ]}}})
    base, prod, staging = FakeSession(), FakeSession(), FakeSession()
    assume_ok(base)
    base.stub("sts", "eu-west-1").add_client_error("assume_role", "AccessDenied", "not authorized")

    prod.stub("cloudwatch", "us-east-1").add_response("describe_alarms", {"MetricAlarms": [
        alarm("a", NOW - timedelta(hours=1)), alarm("b", NOW - timedelta(days=2))]})
    prod.stub("cloudwatch", "eu-west-1").add_response("describe_alarms", {"MetricAlarms": []})
    arn = f"arn:aws:acm:us-east-1:{ACCOUNT}:certificate/c1"
    prod.stub("acm", "us-east-1").add_response("list_certificates", {"CertificateSummaryList": [{"CertificateArn": arn}]})
    prod.stub("acm", "us-east-1").add_response("describe_certificate", cert_detail(arn, 12, type_="IMPORTED"))
    prod.stub("acm", "eu-west-1").add_response("list_certificates", {"CertificateSummaryList": []})
    prod.stub("ce", "us-east-1").add_response("get_cost_and_usage", {"ResultsByTime": ce_days("41.50", "30.25")})

    sessions = iter([prod, staging])
    doc = collect(clients[SLUG], base_session=base, now=NOW, cache_dir=tmp_path,
                  session_factory=lambda creds: next(sessions), environ={"FLEET_EXTERNAL_ID": EXTERNAL_ID})
    base.assert_done()
    prod.assert_done()
    return doc


def test_fixture_is_what_the_collector_writes(tmp_path):
    doc = stubbed_collection(tmp_path)
    schema_validate(doc)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if os.environ.get("FLEET_WRITE_FIXTURE"):
        FIXTURE_PATH.write_text(text)
    assert FIXTURE_PATH.read_text() == text, "run `make fixture` after a deliberate change"
