"""The client read role's permission policy as plain IAM JSON, rendered from the template.

`fleet-client-read-policy.json` is what the hosted /fleet page shows verbatim (the Worker
imports it at build time). It is derived, never edited: `test_rendered_policy_is_current`
fails when it drifts from fleet-client-read-role.yaml; rewrite it with

    FLEET_WRITE_POLICY=1 .venv/bin/pytest -q ../infra/tests/test_policy_json.py   (from collector/)

Rendering: `${AWS::Partition}` becomes `aws`, `${AWS::AccountId}` becomes the placeholder
`CLIENT_ACCOUNT_ID`, and a statement behind `!If [Condition, stmt, NoValue]` is included
(each such condition defaults to true in the template).
"""
import json
from pathlib import Path

import cfn_yaml

AWS_DIR = Path(__file__).resolve().parents[1] / "aws"
TEMPLATE = AWS_DIR / "fleet-client-read-role.yaml"
RENDERED = AWS_DIR / "fleet-client-read-policy.json"
ACCOUNT_PLACEHOLDER = "CLIENT_ACCOUNT_ID"


def _resolve(node):
    if isinstance(node, dict):
        if "Fn::Sub" in node and isinstance(node["Fn::Sub"], str):
            return node["Fn::Sub"].replace("${AWS::Partition}", "aws").replace("${AWS::AccountId}", ACCOUNT_PLACEHOLDER)
        return {k: _resolve(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_resolve(v) for v in node]
    return node


def render(template=TEMPLATE) -> dict:
    t = cfn_yaml.load(template)
    (policy,) = t["Resources"]["ReadRole"]["Properties"]["Policies"]
    doc = policy["PolicyDocument"]
    statements = []
    for s in doc["Statement"]:
        if isinstance(s, dict) and "Fn::If" in s:
            s = s["Fn::If"][1]
        statements.append(_resolve(s))
    out = {"Version": doc["Version"], "Statement": statements}
    assert "Fn::" not in json.dumps(out) and '"Ref"' not in json.dumps(out), "unresolved intrinsic"
    return out


def text(template=TEMPLATE) -> str:
    return json.dumps(render(template), indent=2) + "\n"
