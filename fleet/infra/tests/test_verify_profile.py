"""infra/aws/verify_readonly.py --profile fleet is held to the collector: its required set is
exactly CLIENT_ROLE_ACTIONS, and the client role template passes its policy scan and trust check."""
import json
import sys
from pathlib import Path

import policy_json
from dawnfix_fleet.guard import CLIENT_ROLE_ACTIONS

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "infra" / "aws"))
import verify_readonly as vr  # noqa: E402

FLEET = vr.ROLE_PROFILES["fleet"]


def test_required_set_is_the_collector_allowlist():
    assert set(FLEET.required) == CLIENT_ROLE_ACTIONS
    assert len(FLEET.required) == len(CLIENT_ROLE_ACTIONS)


def test_the_client_template_policy_passes_the_fleet_scan():
    doc = json.loads(policy_json.RENDERED.read_text())
    assert vr.extra_grants([("inline:fleet-read-only", doc)], FLEET.read_only_patterns) == []


def test_the_template_trust_with_an_external_id_passes_and_without_one_fails():
    trust = {"Statement": [{"Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::210987654321:role/hub"},
                            "Action": "sts:AssumeRole",
                            "Condition": {"StringEquals": {"sts:ExternalId": "a-unique-external-id-0001"}}}]}
    assert vr.trust_problems(trust, FLEET.external_id_required) == []
    del trust["Statement"][0]["Condition"]
    assert vr.trust_problems(trust, FLEET.external_id_required)
