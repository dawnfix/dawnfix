"""Structural checks on infra/aws/dawnfix-read-role-bitbucket.yaml: the Bitbucket OIDC trust is
one repository (optionally one deployment environment) of one workspace, exactly; the
permissions are the GitHub role's read set, unchanged."""
import json
import re
from pathlib import Path

import pytest

import cfn_yaml
import verify_readonly as vr

ROOT = Path(__file__).resolve().parents[1] / "aws"
ISSUER = "api.bitbucket.org/2.0/workspaces/${Workspace}/pipelines-config/identity/oidc"


@pytest.fixture(scope="module")
def t():
    return cfn_yaml.load(ROOT / "dawnfix-read-role-bitbucket.yaml")


def test_trust_is_one_repository_with_the_workspace_audience(t):
    text, vars_ = t["Resources"]["ReadRole"]["Properties"]["AssumeRolePolicyDocument"]["Fn::Sub"]
    doc = json.loads(text)
    (st,) = doc["Statement"]
    assert st["Action"] == "sts:AssumeRoleWithWebIdentity" and set(st["Condition"]) == {"StringEquals", "StringLike"}
    assert st["Condition"]["StringEquals"] == {f"{ISSUER}:aud": "ari:cloud:bitbucket::workspace/${WorkspaceUuid}"}
    assert st["Condition"]["StringLike"] == {f"{ISSUER}:sub": "${SubPattern}"}
    assert st["Principal"]["Federated"] == "${ProviderArn}"
    assert vars_["SubPattern"] == {"Fn::If": ["AnyEnvironment", {"Fn::Sub": "${RepositoryUuid}:*"},
                                              {"Fn::Sub": "${RepositoryUuid}:${EnvironmentUuid}:*"}]}
    assert vars_["ProviderArn"] == {"Fn::If": ["CreateProvider", {"Ref": "BitbucketOIDCProvider"},
                                               {"Ref": "ExistingOIDCProviderArn"}]}
    p = t["Resources"]["BitbucketOIDCProvider"]["Properties"]
    assert p["Url"] == {"Fn::Sub": f"https://{ISSUER}"}
    assert p["ClientIdList"] == [{"Fn::Sub": "ari:cloud:bitbucket::workspace/${WorkspaceUuid}"}]
    assert p["ThumbprintList"] == ["a031c46782e6e6c662c2c87c76da9aa62ccabd8e"]


def test_uuid_patterns(t):
    u = "555a99ae-b049-46d1-b165-1eec249d1d8c"
    ws = re.compile(t["Parameters"]["WorkspaceUuid"]["AllowedPattern"])
    repo = re.compile(t["Parameters"]["RepositoryUuid"]["AllowedPattern"])
    env = re.compile(t["Parameters"]["EnvironmentUuid"]["AllowedPattern"])
    assert ws.fullmatch(u) and not ws.fullmatch("{" + u + "}")
    assert repo.fullmatch("{" + u + "}") and not repo.fullmatch(u) and not repo.fullmatch("{*}")
    assert env.fullmatch("") and env.fullmatch("{" + u + "}") and not env.fullmatch("*")
    assert re.compile(t["Parameters"]["Workspace"]["AllowedPattern"]).fullmatch("squalus")


def test_the_same_read_only_policy_as_the_github_role(t):
    gh = cfn_yaml.load(ROOT / "dawnfix-read-role.yaml")
    assert t["Resources"]["ReadRole"]["Properties"]["Policies"] == gh["Resources"]["ReadRole"]["Properties"]["Policies"]
    (pol,) = t["Resources"]["ReadRole"]["Properties"]["Policies"]
    assert vr.extra_grants([("template", {"Statement": pol["PolicyDocument"]["Statement"]})]) == []
    assert t["Outputs"]["RoleArn"]["Value"] == {"Fn::GetAtt": ["ReadRole", "Arn"]}
