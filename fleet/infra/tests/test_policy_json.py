"""The rendered client policy (shown on the hosted /fleet page) matches the template."""
import json
import os

import policy_json
from dawnfix_fleet.guard import CLIENT_ROLE_ACTIONS


def test_rendered_policy_is_current():
    want = policy_json.text()
    if os.environ.get("FLEET_WRITE_POLICY") == "1":
        policy_json.RENDERED.write_text(want)
    assert policy_json.RENDERED.read_text() == want, "fleet-client-read-policy.json is stale: FLEET_WRITE_POLICY=1"


def test_rendered_policy_grants_exactly_the_collector_allowlist():
    doc = json.loads(policy_json.RENDERED.read_text())
    actions = set()
    for s in doc["Statement"]:
        assert s["Effect"] == "Allow"
        actions |= {s["Action"]} if isinstance(s["Action"], str) else set(s["Action"])
    assert actions == CLIENT_ROLE_ACTIONS
    assert "arn:aws:acm:*:CLIENT_ACCOUNT_ID:certificate/*" in [s["Resource"] for s in doc["Statement"]]


def test_rendered_policy_carries_no_brand_or_url():
    raw = policy_json.RENDERED.read_text().lower()
    for word in ("dawnfix", "http", ".ai"):
        assert word not in raw
