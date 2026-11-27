"""verify_readonly against stubbed IAM (botocore Stubber; no network, no credentials)."""
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pytest
from botocore.stub import ANY, Stubber

import cfn_yaml
import verify_readonly as vr

ROLE = "arn:aws:iam::123456789012:role/dawnfix-read"
TEMPLATE = Path(__file__).resolve().parents[1] / "aws" / "dawnfix-read-role.yaml"
GOOD_TRUST = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"},
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {"StringEquals": {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
            "token.actions.githubusercontent.com:sub": "repo:example-org/example-app:ref:refs/heads/main",
        }},
    }],
}


def template_policy():
    t = cfn_yaml.load(TEMPLATE)
    (pol,) = t["Resources"]["ReadRole"]["Properties"]["Policies"]
    return {"Version": "2012-10-17", "Statement": pol["PolicyDocument"]["Statement"]}


def iam_client():
    return boto3.client("iam", region_name="us-east-1", aws_access_key_id="x",
                        aws_secret_access_key="x", aws_session_token="x")


def results(decisions: dict) -> dict:
    return {"EvaluationResults": [
        {"EvalActionName": a, "EvalResourceName": "*", "EvalDecision": d} for a, d in decisions.items()
    ], "IsTruncated": False}


class FakeIam:
    """Builds the exact Stubber call sequence verify() makes."""

    def __init__(self, allowed=(), denied_reads=(), inline=None, attached=(), trust=GOOD_TRUST, log_groups=(),
                 profile=vr.DEFAULT_PROFILE, role=ROLE):
        self.client = iam_client()
        self.stub = Stubber(self.client)
        reads = profile.required + profile.expected
        unscoped = [a for a in reads if a not in profile.log_group_scoped]
        scoped = [a for a in reads if a in profile.log_group_scoped]
        log_writes = [a for a in profile.writes if a.startswith("logs:")]
        if not scoped:
            log_groups = ()
        role_name = role.rsplit("/", 1)[1]

        def decide(actions):
            return {a: ("allowed" if (a in allowed or (a in reads and a not in denied_reads)) else "implicitDeny")
                    for a in actions}

        first = list(profile.writes) + unscoped
        self.stub.add_response("simulate_principal_policy", results(decide(first)),
                               {"PolicySourceArn": role, "ActionNames": first, "ResourceArns": ["*"]})
        for g in log_groups:
            arn = f"arn:aws:logs:us-east-1:123456789012:log-group:{g}"
            acts = scoped + log_writes
            self.stub.add_response("simulate_principal_policy", results(decide(acts)),
                                   {"PolicySourceArn": role, "ActionNames": acts, "ResourceArns": [arn]})
        inline = {"dawnfix-read-only": template_policy()} if inline is None else inline
        self.stub.add_response("list_role_policies", {"PolicyNames": list(inline), "IsTruncated": False},
                               {"RoleName": role_name})
        for name, doc in inline.items():
            self.stub.add_response("get_role_policy", {
                "RoleName": role_name, "PolicyName": name,
                "PolicyDocument": urllib.parse.quote(json.dumps(doc))},
                {"RoleName": role_name, "PolicyName": name})
        self.stub.add_response("list_attached_role_policies", {
            "AttachedPolicies": [{"PolicyName": n, "PolicyArn": f"arn:aws:iam::123456789012:policy/{n}"} for n, _ in attached],
            "IsTruncated": False}, {"RoleName": role_name})
        for n, doc in attached:
            parn = f"arn:aws:iam::123456789012:policy/{n}"
            self.stub.add_response("get_policy", {"Policy": {"PolicyName": n, "Arn": parn, "DefaultVersionId": "v3"}},
                                   {"PolicyArn": parn})
            self.stub.add_response("get_policy_version", {"PolicyVersion": {
                "Document": urllib.parse.quote(json.dumps(doc)), "VersionId": "v3", "IsDefaultVersion": True}},
                {"PolicyArn": parn, "VersionId": "v3"})
        self.stub.add_response("get_role", {"Role": {
            "Path": "/", "RoleName": role_name, "RoleId": "AROAEXAMPLEEXAMPLE1234", "Arn": role,
            "CreateDate": datetime(2026, 10, 27, tzinfo=timezone.utc),
            "AssumeRolePolicyDocument": urllib.parse.quote(json.dumps(trust))}},
            {"RoleName": role_name})
        self.stub.activate()

    def done(self):
        self.stub.assert_no_pending_responses()


def test_template_role_passes(capsys):
    f = FakeIam(log_groups=["my-api-prod"])
    rc = vr.main([ROLE, "--log-group", "my-api-prod"], iam=f.client)
    f.done()
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "read-only, OK" in out


def test_without_log_groups_scoped_reads_are_reported_unchecked():
    f = FakeIam()
    report = vr.verify(f.client, ROLE)
    f.done()
    assert report.ok
    assert report.unchecked and "logs:FilterLogEvents" in report.unchecked[0]


@pytest.mark.parametrize("write", ["logs:DeleteLogGroup", "cloudwatch:PutMetricAlarm", "iam:CreateAccessKey",
                                   "s3:PutObject", "ec2:TerminateInstances", "secretsmanager:GetSecretValue"])
def test_allowed_write_is_refused(write, capsys):
    f = FakeIam(allowed={write})
    rc = vr.main([ROLE, "--json"], iam=f.client)
    f.done()
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert report["allowed_writes"] == [f"{write} on *"]


def test_log_write_scoped_to_a_group_is_caught():
    f = FakeIam(allowed={"logs:PutLogEvents"}, log_groups=["my-api-prod"])
    report = vr.verify(f.client, ROLE, ["my-api-prod"])
    f.done()
    assert "logs:PutLogEvents on my-api-prod" in report.allowed_writes
    assert not report.ok


def test_missing_required_read_is_refused():
    f = FakeIam(denied_reads={"cloudwatch:GetMetricData"})
    report = vr.verify(f.client, ROLE)
    f.done()
    assert report.denied_required == ["cloudwatch:GetMetricData on *"]
    assert not report.ok


def test_missing_optional_read_only_warns():
    f = FakeIam(denied_reads={"logs:GetQueryResults"})
    report = vr.verify(f.client, ROLE)
    f.done()
    assert report.denied_expected == ["logs:GetQueryResults on *"]
    assert report.ok


def test_resource_scoped_write_grant_found_by_policy_scan():
    # The simulator would say implicitDeny for s3:PutObject on "*"; the scan still sees it.
    bucket = {"Statement": [{"Effect": "Allow", "Action": "s3:PutObject", "Resource": "arn:aws:s3:::uploads/*"}]}
    f = FakeIam(attached=[("uploads-writer", bucket)])
    report = vr.verify(f.client, ROLE)
    f.done()
    assert report.extra_grants == ["attached:uploads-writer: s3:PutObject"]
    assert not report.ok


def test_not_action_and_wildcards_are_refused():
    doc = {"Statement": [
        {"Effect": "Allow", "NotAction": "iam:*", "Resource": "*"},
        {"Effect": "Allow", "Action": ["logs:*", "cloudwatch:Get*"], "Resource": "*"},
        {"Effect": "Deny", "Action": "*", "Resource": "*"},
    ]}
    found = vr.extra_grants([("inline:x", doc)])
    assert found == ["inline:x: Allow with NotAction (grants everything not listed)", "inline:x: logs:*"]


def test_trust_without_sub_is_refused():
    trust = json.loads(json.dumps(GOOD_TRUST))
    del trust["Statement"][0]["Condition"]["StringEquals"]["token.actions.githubusercontent.com:sub"]
    f = FakeIam(trust=trust)
    report = vr.verify(f.client, ROLE)
    f.done()
    assert any("without a sub condition" in p for p in report.trust_problems)
    assert not report.ok


def test_trust_with_org_wildcard_is_refused():
    trust = json.loads(json.dumps(GOOD_TRUST))
    cond = trust["Statement"][0]["Condition"]
    sub = cond["StringEquals"].pop("token.actions.githubusercontent.com:sub")
    cond["StringLike"] = {"token.actions.githubusercontent.com:sub": "repo:example-org/*:*"}
    assert sub
    assert vr.trust_problems(trust) == ["sub condition 'repo:example-org/*:*' (StringLike) is not pinned to one repository"]


def test_trust_any_principal_is_refused():
    assert vr.trust_problems({"Statement": [{"Effect": "Allow", "Principal": "*", "Action": "sts:AssumeRole"}]}) \
        == ["trust policy allows any principal"]


def test_simulation_follows_pagination():
    client = iam_client()
    stub = Stubber(client)
    stub.add_response("simulate_principal_policy", {
        "EvaluationResults": [{"EvalActionName": "a:One", "EvalResourceName": "*", "EvalDecision": "allowed"}],
        "IsTruncated": True, "Marker": "m1"}, {"PolicySourceArn": ROLE, "ActionNames": ANY, "ResourceArns": ["*"]})
    stub.add_response("simulate_principal_policy", {
        "EvaluationResults": [{"EvalActionName": "a:Two", "EvalResourceName": "*", "EvalDecision": "explicitDeny"}],
        "IsTruncated": False}, {"PolicySourceArn": ROLE, "ActionNames": ANY, "ResourceArns": ["*"], "Marker": "m1"})
    with stub:
        assert vr.simulate(client, ROLE, ["a:One", "a:Two"]) == {"a:One": "allowed", "a:Two": "explicitDeny"}
    stub.assert_no_pending_responses()


def test_aws_error_exits_2(capsys):
    client = iam_client()
    stub = Stubber(client)
    stub.add_client_error("simulate_principal_policy", service_error_code="AccessDenied", http_status_code=403)
    with stub:
        rc = vr.main([ROLE], iam=client)
    assert rc == 2
    assert "AccessDenied" in capsys.readouterr().err


@pytest.mark.parametrize("arn", ["", "arn:aws:iam::123:user/bob", "arn:aws:s3:::bucket", "dawnfix-read"])
def test_bad_arn_exits_2(arn):
    assert vr.main([arn], iam=object()) == 2


def test_role_with_path_and_partition():
    assert vr.parse_role_arn("arn:aws-us-gov:iam::123456789012:role/ci/dawnfix-read") == \
        ("aws-us-gov", "123456789012", "dawnfix-read")


@pytest.mark.parametrize("action,ok", [
    ("logs:FilterLogEvents", True), ("logs:Describe*", True), ("LOGS:DescribeLogGroups", True),
    ("cloudwatch:GetMetricData", True), ("elasticloadbalancing:DescribeTargetHealth", True),
    ("logs:*", False), ("logs:D*", False), ("*", False), ("logs:PutLogEvents", False),
    ("cloudwatch:PutMetricAlarm", False), ("s3:GetObject", False), ("elasticloadbalancing:*", False),
])
def test_action_is_read_only(action, ok):
    assert vr.action_is_read_only(action) is ok


def test_write_list_is_disjoint_from_read_scope():
    assert not [a for a in vr.WRITE_ACTIONS if vr.action_is_read_only(a)]
    assert all(vr.action_is_read_only(a) for a in vr.REQUIRED_READ_ACTIONS + vr.EXPECTED_READ_ACTIONS)


def test_required_reads_match_what_core_calls():
    core = pytest.importorskip("dawnfix_core.sources.aws")
    assert sorted(a.split(":", 1)[1] for a in vr.REQUIRED_READ_ACTIONS) == sorted(core.READ_ONLY_OPERATIONS)
