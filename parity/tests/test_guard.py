import json
import re
from pathlib import Path

import pytest
from botocore.stub import Stubber

from dawnfix_parity.aws import READ_ONLY_OPERATIONS, VALUE_OPERATIONS, ReadOnlyViolation, make_client

IAM = Path(__file__).resolve().parent.parent / "iam"
SERVICE_PREFIX = {"ssm": "ssm", "secretsmanager": "secretsmanager", "ecs": "ecs", "lambda": "lambda",
                  "cloudtrail": "cloudtrail", "sts": "sts"}


@pytest.mark.parametrize("service, method, kwargs", [
    ("ssm", "put_parameter", {"Name": "/x", "Value": "v", "Type": "String"}),
    ("ssm", "delete_parameter", {"Name": "/x"}),
    ("ssm", "label_parameter_version", {"Name": "/x", "Labels": ["a"]}),
    ("secretsmanager", "put_secret_value", {"SecretId": "x", "SecretString": "v"}),
    ("secretsmanager", "delete_secret", {"SecretId": "x"}),
    ("secretsmanager", "rotate_secret", {"SecretId": "x"}),
    ("ecs", "register_task_definition", {"family": "f", "containerDefinitions": []}),
    ("ecs", "update_service", {"service": "s"}),
    ("lambda", "update_function_configuration", {"FunctionName": "f"}),
    ("lambda", "get_function", {"FunctionName": "f"}),     # a read, but not on the list: refused too
    ("cloudtrail", "stop_logging", {"Name": "t"}),
])
def test_guard_refuses_unlisted_calls_before_sending(session, service, method, kwargs):
    c = make_client(session, service, "eu-central-1")
    sent = []
    c.meta.events.register("before-send", lambda **kw: sent.append(kw) or pytest.fail("request was sent"))
    with pytest.raises(ReadOnlyViolation, match="read-only"):
        getattr(c, method)(**kwargs)
    assert sent == []


def test_guard_allows_listed_call(session):
    c = make_client(session, "ssm", "eu-central-1")
    with Stubber(c) as s:
        s.add_response("describe_parameters", {"Parameters": []})
        assert c.describe_parameters() == {"Parameters": []}


def test_allowlist_is_read_verbs_only():
    for op in READ_ONLY_OPERATIONS:
        assert re.match(r"^(Describe|List|Get|Lookup|AssumeRole$)", op), op
    assert VALUE_OPERATIONS <= set(READ_ONLY_OPERATIONS)


def _actions(path):
    doc = json.loads(path.read_text())
    out = set()
    for st in doc["Statement"]:
        assert st["Effect"] == "Allow"
        acts = st["Action"] if isinstance(st["Action"], list) else [st["Action"]]
        out |= set(acts)
    return out


def test_iam_policy_matches_allowlist():
    base = _actions(IAM / "parity-read-only-policy.json")
    addon = _actions(IAM / "parity-hash-mode-addon.json")
    ops = {a.split(":", 1)[1] for a in base | addon if not a.startswith("kms:")}
    # every allowed operation except AssumeRole (granted on the CI role) is in a policy, and nothing else
    assert ops == set(READ_ONLY_OPERATIONS) - {"AssumeRole"}
    # value-reading actions live only in the opt-in add-on
    assert {a.split(":", 1)[1] for a in addon if not a.startswith("kms:")} == VALUE_OPERATIONS
    assert not ({a.split(":", 1)[1] for a in base} & VALUE_OPERATIONS)
    assert not any("*" in a for a in base | addon)
    assert all(re.match(r"^\w+:(Describe|List|Get|Lookup|Decrypt)", a) for a in base | addon)


def test_guard_runs_before_a_stubber(session):
    """Even with a response queued for a write, the guard refuses it first."""
    c = make_client(session, "ssm", "eu-central-1")
    with Stubber(c) as s:
        s.add_response("put_parameter", {"Version": 1})
        with pytest.raises(ReadOnlyViolation):
            c.put_parameter(Name="/x", Value="v", Type="String")


def test_guard_is_dawnfix_cores():
    import dawnfix_core.awsguard as core
    from dawnfix_parity import aws

    assert aws.ReadOnlyViolation is core.ReadOnlyViolation


def test_each_client_gets_only_its_own_services_operations(session):
    from dawnfix_parity.aws import SERVICE_OPERATIONS

    ssm = make_client(session, "ssm", "eu-central-1")
    sent = []
    ssm.meta.events.register("before-send", lambda **kw: sent.append(kw))
    # ListSecrets is on parity's list, but not for an SSM client; GetParameter (singular) never
    with pytest.raises(ReadOnlyViolation) as e:
        ssm.get_parameter(Name="/x")
    assert e.value.operation == "GetParameter"
    assert sent == []
    assert set().union(*SERVICE_OPERATIONS.values()) == set(READ_ONLY_OPERATIONS)
    s3 = make_client(session, "s3", "eu-central-1")
    with pytest.raises(ReadOnlyViolation):
        s3.list_buckets()


def test_guard_refuses_at_the_first_event(session):
    """provide-client-params fires before botocore validates parameters: an invalid write is
    refused by the guard, not rejected by the parameter validator."""
    c = make_client(session, "ssm", "eu-central-1")
    with pytest.raises(ReadOnlyViolation):
        c.put_parameter()    # missing required params: the validator would raise otherwise
