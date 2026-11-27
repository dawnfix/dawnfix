"""Stubbed AWS only: real botocore clients with Stubber, fake credentials, no network."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
import jsonschema
import pytest
from botocore.stub import ANY, Stubber

from dawnfix_fleet.config import parse

FLEET = Path(__file__).resolve().parents[2]
SCHEMA_PATH = FLEET / "schema" / "fleet-summary.schema.json"
FIXTURE_PATH = FLEET / "fixtures" / "summary.json"
NOW = datetime(2026, 10, 27, 6, 5, tzinfo=timezone.utc)
SLUG = "k3m9x2a7b4cd"
ACCOUNT = "111122223333"
ROLE = f"arn:aws:iam::{ACCOUNT}:role/fleet-read"
EXTERNAL_ID = "fleet-4f1c2b9e7d6a5c3b"


def schema():
    return json.loads(SCHEMA_PATH.read_text())


def schema_validate(doc):
    jsonschema.Draft202012Validator(schema()).validate(doc)


class FakeSession:
    """Hands out pre-stubbed clients by (service, region). A client nobody stubbed is a test bug."""

    def __init__(self):
        self.clients = {}
        self.stubs = {}

    def stub(self, service, region):
        key = (service, region)
        if key not in self.stubs:
            c = boto3.client(service, region_name=region, aws_access_key_id="AKIDTEST",
                             aws_secret_access_key="secret", aws_session_token="token")
            s = Stubber(c)
            s.activate()
            self.clients[key] = c
            self.stubs[key] = s
        return self.stubs[key]

    def client(self, service, region_name=None):
        return self.clients[(service, region_name)]

    def assert_done(self):
        for s in self.stubs.values():
            s.assert_no_pending_responses()


def config(**account):
    acct = {"provider": "aws", "env": "prod", "account_id": ACCOUNT, "role_arn": ROLE,
            "external_id_env": "FLEET_EXTERNAL_ID", "regions": ["us-east-1"], **account}
    acct = {k: v for k, v in acct.items() if v is not None}
    return parse({"version": 1, "clients": {SLUG: {"accounts": [acct]}}})


def assume_ok(base: FakeSession, region="us-east-1", account=ACCOUNT, external_id=EXTERNAL_ID):
    base.stub("sts", region).add_response(
        "assume_role",
        {
            "Credentials": {"AccessKeyId": "ASIATESTTESTTEST0000", "SecretAccessKey": "s", "SessionToken": "t",
                            "Expiration": NOW + timedelta(minutes=15)},
            "AssumedRoleUser": {"AssumedRoleId": "AROATEST:fleet-collect",
                                "Arn": f"arn:aws:sts::{account}:assumed-role/fleet-read/fleet-collect"},
        },
        {"RoleArn": ROLE, "RoleSessionName": "fleet-collect", "ExternalId": external_id, "DurationSeconds": 900},
    )


def alarm(name, updated):
    return {"AlarmName": name, "StateValue": "ALARM", "StateUpdatedTimestamp": updated}


def cert_detail(arn, days, in_use=True, type_="AMAZON_ISSUED", renewal="ELIGIBLE"):
    c = {"CertificateArn": arn, "Type": type_, "RenewalEligibility": renewal,
         "NotAfter": NOW + timedelta(days=days, hours=1), "InUseBy": [f"{arn}-lb"] if in_use else []}
    return {"Certificate": c}


def ce_day(day, amount, unit="USD"):
    return {"TimePeriod": {"Start": day, "End": day}, "Total": {"UnblendedCost": {"Amount": amount, "Unit": unit}},
            "Groups": [], "Estimated": False}


def ce_days(this_week_each="10.005", last_week_each="8.00", unit="USD"):
    from datetime import date

    today = NOW.date()
    out = []
    for i in range(14, 0, -1):
        d = (today - timedelta(days=i)).isoformat()
        out.append(ce_day(d, this_week_each if i <= 7 else last_week_each, unit))
    return out


@pytest.fixture
def env():
    return {"FLEET_EXTERNAL_ID": EXTERNAL_ID}


__all__ = ["ANY"]
