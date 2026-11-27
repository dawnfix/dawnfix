import json
from pathlib import Path

from logbill.awsread import INSIGHTS_OPERATIONS, READ_OPERATIONS, WRITE_OPERATIONS

IAM = Path(__file__).resolve().parent.parent / "iam"
# GetCallerIdentity needs no IAM permission.
NEEDS_NO_PERMISSION = {"GetCallerIdentity"}
SERVICE = {"GetMetricData": "cloudwatch"}


def _actions(name):
    doc = json.loads((IAM / name).read_text())
    return {a for st in doc["Statement"] for a in st["Action"]}


def _iam(ops):
    return {f"{SERVICE.get(op, 'logs')}:{op}" for op in ops if op not in NEEDS_NO_PERMISSION}


def test_default_policy_is_exactly_the_scan_allowlists():
    acts = _actions("logbill-readonly-policy.json")
    assert acts == _iam(READ_OPERATIONS | INSIGHTS_OPERATIONS)
    for a in acts:
        verb = a.split(":")[1]
        assert verb.startswith(("Describe", "Get", "StartQuery", "StopQuery")), a
        assert not verb.startswith(("Put", "Delete", "Create", "Update", "Tag", "Associate")), a


def test_apply_policy_is_only_put_retention():
    assert _actions("logbill-apply-retention-policy.json") == _iam(WRITE_OPERATIONS) == {"logs:PutRetentionPolicy"}
