"""Structural checks on infra/aws/dawnfix-read-role.yaml (stand-in for cfn-lint)."""
import re
from pathlib import Path

import pytest

import cfn_yaml
import verify_readonly as vr

TEMPLATE = Path(__file__).resolve().parents[1] / "aws" / "dawnfix-read-role.yaml"
PSEUDO = {"AWS::AccountId", "AWS::Partition", "AWS::Region", "AWS::StackName", "AWS::StackId",
          "AWS::URLSuffix", "AWS::NoValue", "AWS::NotificationARNs"}


@pytest.fixture(scope="module")
def t():
    return cfn_yaml.load(TEMPLATE)


def _walk(node):
    yield node
    if isinstance(node, dict):
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def test_top_level(t):
    assert t["AWSTemplateFormatVersion"] == "2010-09-09"
    assert set(t) <= {"AWSTemplateFormatVersion", "Description", "Metadata", "Parameters",
                      "Rules", "Conditions", "Resources", "Outputs"}
    assert {"GitHubOrg", "GitHubRepo", "Branch", "Environment", "CreateOIDCProvider",
            "ExistingOIDCProviderArn", "LogGroupPrefix"} <= set(t["Parameters"])
    assert t["Parameters"]["Branch"]["Default"] == "main"
    assert t["Parameters"]["LogGroupPrefix"]["Default"] == "*"
    assert t["Parameters"]["CreateOIDCProvider"]["AllowedValues"] == ["true", "false"]


def test_references_resolve(t):
    names = set(t["Parameters"]) | set(t["Resources"]) | PSEUDO
    conditions = set(t["Conditions"])
    for node in _walk(t):
        if not isinstance(node, dict):
            continue
        if "Ref" in node:
            assert node["Ref"] in names, node
        if "Fn::GetAtt" in node:
            assert node["Fn::GetAtt"][0] in t["Resources"], node
        if "Fn::If" in node:
            assert node["Fn::If"][0] in conditions, node
        if "Fn::Sub" in node and isinstance(node["Fn::Sub"], str):
            for var in re.findall(r"\$\{([^}!]+)\}", node["Fn::Sub"]):
                assert var in names, var
    for name, res in t["Resources"].items():
        if "Condition" in res:
            assert res["Condition"] in conditions, name


def test_parameter_patterns_compile_and_accept_defaults(t):
    for name, p in t["Parameters"].items():
        if "AllowedPattern" in p:
            rx = re.compile(p["AllowedPattern"])
            if "Default" in p:
                assert rx.fullmatch(p["Default"]), name
    rx = re.compile(t["Parameters"]["LogGroupPrefix"]["AllowedPattern"])
    assert rx.fullmatch("ecs-*") and rx.fullmatch("/aws/lambda/api-*")
    assert not rx.fullmatch("ecs-api")  # must end in *


def test_existing_provider_rule(t):
    rule = t["Rules"]["ExistingProviderGiven"]
    assert rule["RuleCondition"] == {"Fn::Equals": [{"Ref": "CreateOIDCProvider"}, "false"]}
    assert rule["Assertions"][0]["Assert"] == {"Fn::Not": [{"Fn::Equals": [{"Ref": "ExistingOIDCProviderArn"}, ""]}]}


def test_trust_policy(t):
    role = t["Resources"]["ReadRole"]["Properties"]
    assert role["MaxSessionDuration"] == 3600
    (st,) = role["AssumeRolePolicyDocument"]["Statement"]
    assert st["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert st["Principal"]["Federated"] == {"Fn::If": ["CreateProvider", {"Ref": "GitHubOIDCProvider"},
                                                      {"Ref": "ExistingOIDCProviderArn"}]}
    eq = st["Condition"]["StringEquals"]
    assert eq["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    sub = eq["token.actions.githubusercontent.com:sub"]["Fn::If"]
    assert sub[0] == "HasEnvironment"
    assert sub[1] == {"Fn::Sub": "repo:${GitHubOrg}/${GitHubRepo}:environment:${Environment}"}
    assert sub[2] == {"Fn::Sub": "repo:${GitHubOrg}/${GitHubRepo}:ref:refs/heads/${Branch}"}
    # No StringLike anywhere: the sub is an exact match.
    assert "StringLike" not in st["Condition"]
    provider = t["Resources"]["GitHubOIDCProvider"]
    assert provider["Condition"] == "CreateProvider"
    assert provider["Properties"]["ClientIdList"] == ["sts.amazonaws.com"]


def _policy_actions(t):
    (pol,) = t["Resources"]["ReadRole"]["Properties"]["Policies"]
    return pol["PolicyDocument"]["Statement"]


def test_policy_is_exactly_the_read_set(t):
    actions = sorted(a for st in _policy_actions(t) for a in st["Action"])
    assert actions == sorted([
        "logs:FilterLogEvents", "logs:GetLogEvents", "logs:StartQuery",
        "logs:Describe*", "logs:StopQuery", "logs:GetQueryResults",
        "cloudwatch:DescribeAlarms", "cloudwatch:GetMetricData", "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics",
        "elasticloadbalancing:DescribeLoadBalancers", "elasticloadbalancing:DescribeTargetGroups",
        "elasticloadbalancing:DescribeTargetHealth",
    ])
    assert all(st["Effect"] == "Allow" and "NotAction" not in st for st in _policy_actions(t))


def test_policy_passes_the_verifier_scan(t):
    doc = {"Statement": _policy_actions(t)}
    assert vr.extra_grants([("template", doc)]) == []


def test_policy_covers_what_core_calls(t):
    granted = [a for st in _policy_actions(t) for a in st["Action"]]
    for needed in vr.REQUIRED_READ_ACTIONS:
        assert needed in granted


def test_log_reads_are_scoped_by_prefix(t):
    scoped = next(st for st in _policy_actions(t) if st["Sid"] == "ReadLogEventsInScope")
    assert scoped["Resource"] == {
        "Fn::Sub": "arn:${AWS::Partition}:logs:*:${AWS::AccountId}:log-group:${LogGroupPrefix}"}


def test_outputs(t):
    assert t["Outputs"]["RoleArn"]["Value"] == {"Fn::GetAtt": ["ReadRole", "Arn"]}
