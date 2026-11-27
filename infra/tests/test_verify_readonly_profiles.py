"""verify_readonly --profile: the role profiles (dawnfix, the default, and fleet: the agency
board's per-client read role) against stubbed IAM. No network, no credentials."""
import json

import pytest

import verify_readonly as vr
from test_verify_readonly import FakeIam

FLEET_ROLE = "arn:aws:iam::123456789012:role/fleet-read"
FLEET_POLICY = {"Version": "2012-10-17", "Statement": [
    {"Effect": "Allow", "Action": ["cloudwatch:DescribeAlarms"], "Resource": "*"},
    {"Effect": "Allow", "Action": ["acm:ListCertificates"], "Resource": "*"},
    {"Effect": "Allow", "Action": ["acm:DescribeCertificate"], "Resource": "arn:aws:acm:*:123456789012:certificate/*"},
    {"Effect": "Allow", "Action": ["ce:GetCostAndUsage"], "Resource": "*"},
]}
AGENCY_TRUST = {"Version": "2012-10-17", "Statement": [{
    "Effect": "Allow",
    "Principal": {"AWS": "arn:aws:iam::210987654321:role/fleet-hub"},
    "Action": "sts:AssumeRole",
    "Condition": {"StringEquals": {"sts:ExternalId": "x7Q2-random-external-id-for-one-client"}},
}]}
FLEET = vr.ROLE_PROFILES["fleet"]


def fleet(**kw):
    kw.setdefault("inline", {"fleet-read-only": FLEET_POLICY})
    kw.setdefault("trust", AGENCY_TRUST)
    return FakeIam(profile=FLEET, role=FLEET_ROLE, **kw)


def test_profiles_and_the_fleet_required_set():
    assert set(vr.ROLE_PROFILES) == {"dawnfix", "fleet"}
    assert vr.ROLE_PROFILES["dawnfix"].required == vr.REQUIRED_READ_ACTIONS
    assert set(FLEET.required) == {"cloudwatch:DescribeAlarms", "acm:ListCertificates", "acm:DescribeCertificate",
                                   "ce:GetCostAndUsage"}
    assert not set(FLEET.required) & set(FLEET.writes)


def test_the_fleet_role_passes(capsys):
    f = fleet()
    rc = vr.main([FLEET_ROLE, "--profile", "fleet"], iam=f.client)
    f.done()
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "read-only, OK" in out


def test_a_dawnfix_read_role_is_not_a_fleet_role():
    """Its log and metric grants are outside the fleet scope, and it lacks ACM and CE."""
    f = fleet(inline=None, denied_reads={"acm:ListCertificates", "acm:DescribeCertificate", "ce:GetCostAndUsage"})
    report = vr.verify(f.client, FLEET_ROLE, profile=FLEET)
    f.done()
    assert not report.ok
    assert "acm:ListCertificates on *" in report.denied_required
    assert any("logs:" in g for g in report.extra_grants)


@pytest.mark.parametrize("extra", ["acm:Describe*", "acm:ExportCertificate", "logs:FilterLogEvents", "cloudwatch:GetMetricData",
                                   "ce:*"])
def test_anything_beyond_the_four_actions_is_refused(extra):
    policy = {"Version": "2012-10-17", "Statement": FLEET_POLICY["Statement"] + [
        {"Effect": "Allow", "Action": extra, "Resource": "*"}]}
    f = fleet(inline={"fleet-read-only": policy})
    report = vr.verify(f.client, FLEET_ROLE, profile=FLEET)
    f.done()
    assert report.extra_grants == [f"inline:fleet-read-only: {extra}"]


@pytest.mark.parametrize("write", ["acm:ExportCertificate", "acm:DeleteCertificate", "cloudwatch:DeleteAlarms",
                                   "logs:FilterLogEvents", "sts:AssumeRole"])
def test_allowed_write_or_out_of_scope_read_is_refused(write):
    f = fleet(allowed={write})
    report = vr.verify(f.client, FLEET_ROLE, profile=FLEET)
    f.done()
    assert report.allowed_writes == [f"{write} on *"]


@pytest.mark.parametrize("condition", [None, {"StringEquals": {"sts:ExternalId": ""}},
                                       {"StringLike": {"sts:ExternalId": "*"}}, {"Bool": {"aws:SecureTransport": "true"}}])
def test_cross_account_trust_needs_an_exact_external_id(condition):
    st = dict(AGENCY_TRUST["Statement"][0])
    st.pop("Condition")
    if condition:
        st["Condition"] = condition
    f = fleet(trust={"Version": "2012-10-17", "Statement": [st]})
    report = vr.verify(f.client, FLEET_ROLE, profile=FLEET)
    f.done()
    assert report.trust_problems == ["cross-account trust without an exact sts:ExternalId condition (confused deputy)"]


def test_log_groups_are_ignored_for_a_role_that_reads_no_logs():
    f = fleet()
    report = vr.verify(f.client, FLEET_ROLE, ["my-api-prod"], profile=FLEET)
    f.done()
    assert report.ok
    assert report.unchecked == ["--log-group ignored: the fleet role reads no logs"]


def test_an_old_style_aws_profile_still_works(capsys, monkeypatch):
    import boto3

    seen = {}

    class Session:
        def __init__(self, profile_name=None):
            seen["profile"] = profile_name

        def client(self, name):
            raise RuntimeError("no network in tests")

    monkeypatch.setattr(boto3.session, "Session", Session)
    assert vr.main([FLEET_ROLE, "--profile", "admin"]) == 2
    assert seen["profile"] == "admin"
    assert "not a role profile; using it as --aws-profile" in capsys.readouterr().err
    assert vr.main([FLEET_ROLE, "--profile", "fleet", "--aws-profile", "admin", "--json"]) == 2
    assert seen["profile"] == "admin"
