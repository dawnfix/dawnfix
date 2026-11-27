"""Structural checks on the fleet CloudFormation templates (stand-in for cfn-lint), and the
one that matters most: the client role grants exactly what the collector's guard allows."""
import re
from pathlib import Path

import pytest

import cfn_yaml
from dawnfix_fleet.guard import CLIENT_ROLE_ACTIONS, READ_ONLY_OPERATIONS

AWS_DIR = Path(__file__).resolve().parents[1] / "aws"
CLIENT = AWS_DIR / "fleet-client-read-role.yaml"
HUB = AWS_DIR / "fleet-agency-hub-role.yaml"
PSEUDO = {"AWS::AccountId", "AWS::Partition", "AWS::Region", "AWS::StackName", "AWS::StackId",
          "AWS::URLSuffix", "AWS::NoValue", "AWS::NotificationARNs"}
WRITE_VERBS = re.compile(r":(Put|Create|Delete|Update|Set|Tag|Untag|Attach|Detach|Modify|Import|Export|"
                         r"Request|Renew|Resend|Enable|Disable|Pass|Get(SecretValue|Object|Parameter))")


def _walk(node):
    yield node
    if isinstance(node, dict):
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _statements(policy_statements):
    """Flatten !If [cond, stmt, NoValue] into the statements it can produce."""
    for s in policy_statements:
        if isinstance(s, dict) and "Fn::If" in s:
            for branch in s["Fn::If"][1:]:
                if branch != {"Ref": "AWS::NoValue"}:
                    yield branch
        else:
            yield s


def _actions(stmt):
    a = stmt["Action"]
    return [a] if isinstance(a, str) else list(a)


@pytest.fixture(scope="module", params=[CLIENT, HUB], ids=["client", "hub"])
def template(request):
    return cfn_yaml.load(request.param)


@pytest.fixture(scope="module")
def client():
    return cfn_yaml.load(CLIENT)


def test_top_level_and_references_resolve(template):
    t = template
    assert t["AWSTemplateFormatVersion"] == "2010-09-09"
    assert set(t) <= {"AWSTemplateFormatVersion", "Description", "Metadata", "Parameters", "Rules", "Conditions",
                      "Resources", "Outputs"}
    names = set(t["Parameters"]) | set(t["Resources"]) | PSEUDO
    conditions = set(t.get("Conditions", {}))
    for node in _walk({k: v for k, v in t.items() if k != "Rules"}):
        if not isinstance(node, dict):
            continue
        if "Ref" in node:
            assert node["Ref"] in names, node
        if "Fn::GetAtt" in node:
            assert node["Fn::GetAtt"][0] in t["Resources"], node
        if "Fn::If" in node:
            assert node["Fn::If"][0] in conditions, node
        if "Condition" in node and isinstance(node["Condition"], str):
            assert node["Condition"] in conditions, node
        if "Fn::Sub" in node and isinstance(node["Fn::Sub"], str):
            for var in re.findall(r"\$\{([^}!]+)\}", node["Fn::Sub"]):
                assert var in names, var
    for p in t["Parameters"].values():
        if "AllowedPattern" in p and "Default" in p:
            assert re.fullmatch(p["AllowedPattern"], p["Default"]), p


def test_client_role_grants_exactly_what_the_collector_calls(client):
    policy = client["Resources"]["ReadRole"]["Properties"]["Policies"]
    assert len(policy) == 1
    granted = set()
    for stmt in _statements(policy[0]["PolicyDocument"]["Statement"]):
        assert stmt["Effect"] == "Allow"
        for action in _actions(stmt):
            assert "*" not in action, action
            assert not WRITE_VERBS.search(action), action
            granted.add(action)
    assert granted == set(CLIENT_ROLE_ACTIONS)
    assert "ce:GetCostAndUsage" in {f"ce:{op}" for op in READ_ONLY_OPERATIONS["ce"]}


def test_cost_explorer_can_be_left_out(client):
    stmts = client["Resources"]["ReadRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
    conditional = [s for s in stmts if "Fn::If" in s]
    assert len(conditional) == 1 and conditional[0]["Fn::If"][0] == "CostExplorer"
    assert _actions(conditional[0]["Fn::If"][1]) == ["ce:GetCostAndUsage"]


def test_agency_trust_requires_the_external_id_and_one_principal(client):
    trust = client["Resources"]["ReadRole"]["Properties"]["AssumeRolePolicyDocument"]["Statement"]
    agency = [s for s in _statements(trust) if s.get("Sid") == "AgencyCollectorWithExternalId"]
    assert len(agency) == 1
    s = agency[0]
    assert s["Action"] == "sts:AssumeRole"
    assert s["Principal"] == {"AWS": {"Ref": "AgencyPrincipalArn"}}
    assert s["Condition"] == {"StringEquals": {"sts:ExternalId": {"Ref": "ExternalId"}}}
    # And the template refuses to deploy an agency trust with no External ID.
    rule = client["Rules"]["AgencyNeedsExternalId"]
    assert rule["Assertions"][0]["Assert"] == {"Fn::Not": [{"Fn::Equals": [{"Ref": "ExternalId"}, ""]}]}
    p = client["Parameters"]["ExternalId"]
    assert p["NoEcho"] is True
    assert not re.fullmatch(p["AllowedPattern"], "short")
    assert re.fullmatch(p["AllowedPattern"], "fleet-4f1c2b9e7d6a5c3b")


def test_github_trust_pins_audience_and_subject(client):
    trust = client["Resources"]["ReadRole"]["Properties"]["AssumeRolePolicyDocument"]["Statement"]
    gh = [s for s in _statements(trust) if s.get("Sid") == "GitHubOIDCThisRepoOnly"][0]
    eq = gh["Condition"]["StringEquals"]
    assert eq["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    assert eq["token.actions.githubusercontent.com:sub"] == {
        "Fn::Sub": "repo:${GitHubOrg}/${GitHubRepo}:ref:refs/heads/${Branch}"}


def test_hub_can_only_assume_the_client_read_role():
    hub = cfn_yaml.load(HUB)
    stmts = hub["Resources"]["HubRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
    assert len(stmts) == 1
    assert stmts[0]["Action"] == "sts:AssumeRole"
    assert stmts[0]["Resource"] == {"Fn::Sub": "arn:${AWS::Partition}:iam::*:role/${ClientRoleName}"}


def test_no_brand_or_client_names_in_templates():
    for path in (CLIENT, HUB):
        text = path.read_text().lower()
        assert "dawnfix" not in text.replace("the dawnfix read role", "")
