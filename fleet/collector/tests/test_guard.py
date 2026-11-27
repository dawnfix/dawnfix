import boto3
import pytest

from dawnfix_fleet.guard import CLIENT_ROLE_ACTIONS, READ_ONLY_OPERATIONS, ReadOnlyViolation, make_client

from .conftest import FakeSession


def test_refuses_any_operation_outside_the_allowlist_before_it_is_built():
    base = FakeSession()
    base.stub("cloudwatch", "us-east-1")  # no responses queued: a call that got through would fail differently
    cw = make_client(base, "cloudwatch", "us-east-1")
    with pytest.raises(ReadOnlyViolation, match="cloudwatch:DeleteAlarms"):
        cw.delete_alarms(AlarmNames=["x"])
    with pytest.raises(ReadOnlyViolation, match="cloudwatch:PutMetricAlarm"):
        cw.put_metric_alarm(AlarmName="x", EvaluationPeriods=1, ComparisonOperator="GreaterThanThreshold")
    base.stub("acm", "us-east-1")
    acm = make_client(base, "acm", "us-east-1")
    with pytest.raises(ReadOnlyViolation):
        acm.export_certificate(CertificateArn="arn:aws:acm:us-east-1:111122223333:certificate/x", Passphrase=b"p")


def test_refuses_services_it_has_no_reason_to_touch():
    session = boto3.session.Session(aws_access_key_id="a", aws_secret_access_key="b", region_name="us-east-1")
    for service in ("s3", "iam", "secretsmanager", "ec2"):
        with pytest.raises(ReadOnlyViolation, match="service"):
            make_client(session, service, "us-east-1")


def test_every_allowed_operation_is_a_read():
    for service, ops in READ_ONLY_OPERATIONS.items():
        for op in ops:
            assert op.startswith(("Describe", "List", "Get", "AssumeRole")), (service, op)


def test_the_client_role_needs_exactly_the_non_sts_operations():
    wanted = {f"{s}:{op}" for s, ops in READ_ONLY_OPERATIONS.items() if s != "sts" for op in ops}
    assert wanted == CLIENT_ROLE_ACTIONS


def test_the_guard_is_core_s_public_one():
    from dawnfix_core import awsguard

    assert ReadOnlyViolation is awsguard.ReadOnlyViolation
    base = FakeSession()
    base.stub("ce", "us-east-1")
    ce = make_client(base, "ce", "us-east-1")
    with pytest.raises(awsguard.ReadOnlyViolation) as refused:
        ce.delete_anomaly_monitor(MonitorArn="arn:aws:ce::111122223333:anomalymonitor/x")
    assert (refused.value.service, refused.value.operation) == ("ce", "DeleteAnomalyMonitor")
    with pytest.raises(awsguard.ReadOnlyViolation) as other:
        make_client(base, "s3", "us-east-1")
    assert other.value.service == "s3"
