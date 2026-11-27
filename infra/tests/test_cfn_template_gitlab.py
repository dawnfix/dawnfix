"""Structural checks on infra/aws/dawnfix-read-role-gitlab.yaml: the GitLab OIDC trust is one
project on one branch, exactly; the permissions are the GitHub role's read set, unchanged."""
import re
from pathlib import Path

import pytest

import cfn_yaml
import verify_readonly as vr

ROOT = Path(__file__).resolve().parents[1] / "aws"


@pytest.fixture(scope="module")
def t():
    return cfn_yaml.load(ROOT / "dawnfix-read-role-gitlab.yaml")


def test_trust_is_one_project_on_one_branch(t):
    (st,) = t["Resources"]["ReadRole"]["Properties"]["AssumeRolePolicyDocument"]["Statement"]
    assert st["Action"] == "sts:AssumeRoleWithWebIdentity" and set(st["Condition"]) == {"StringEquals"}
    eq = st["Condition"]["StringEquals"]
    assert eq["gitlab.com:aud"] == {"Ref": "GitLabUrl"}
    assert eq["gitlab.com:sub"] == {"Fn::Sub": "project_path:${ProjectPath}:ref_type:branch:ref:${Branch}"}
    assert st["Principal"]["Federated"] == {"Fn::If": ["CreateProvider", {"Ref": "GitLabOIDCProvider"},
                                                      {"Ref": "ExistingOIDCProviderArn"}]}
    p = t["Resources"]["GitLabOIDCProvider"]["Properties"]
    assert p["Url"] == {"Ref": "GitLabUrl"} and p["ClientIdList"] == [{"Ref": "GitLabUrl"}]
    assert t["Parameters"]["GitLabUrl"]["AllowedValues"] == ["https://gitlab.com"]


def test_project_path_pattern(t):
    rx = re.compile(t["Parameters"]["ProjectPath"]["AllowedPattern"])
    assert rx.fullmatch("dawnfix-test/sample-app") and rx.fullmatch("acme/platform/shop-api")
    assert not rx.fullmatch("shop-api") and not rx.fullmatch("acme/*")


def test_the_same_read_only_policy_as_the_github_role(t):
    gh = cfn_yaml.load(ROOT / "dawnfix-read-role.yaml")
    assert t["Resources"]["ReadRole"]["Properties"]["Policies"] == gh["Resources"]["ReadRole"]["Properties"]["Policies"]
    (pol,) = t["Resources"]["ReadRole"]["Properties"]["Policies"]
    assert vr.extra_grants([("template", {"Statement": pol["PolicyDocument"]["Statement"]})]) == []
    assert t["Outputs"]["RoleArn"]["Value"] == {"Fn::GetAtt": ["ReadRole", "Arn"]}
