"""The public read-only guard: make_client(session, service, region, allowed=None)."""
import boto3
import pytest
from botocore.stub import Stubber

from dawnfix_core import awsguard
from dawnfix_core.awsguard import DEFAULT_ALLOWED, ReadOnlyViolation, make_client
from dawnfix_core.sources import aws as aws_source


@pytest.fixture
def session():
    return boto3.session.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name="us-east-1")


def test_same_names_from_the_source_module():
    """Older callers (logbill, the tests) import these from sources.aws; they must be the same objects."""
    assert aws_source.ReadOnlyViolation is ReadOnlyViolation
    assert aws_source.make_client is make_client
    assert aws_source.READ_ONLY_OPERATIONS == awsguard.READ_ONLY_OPERATIONS == frozenset({
        "FilterLogEvents", "DescribeAlarms", "GetMetricData", "DescribeLoadBalancers", "DescribeTargetGroups"})


def test_default_allowlists_are_per_service():
    assert DEFAULT_ALLOWED["logs"] == {"FilterLogEvents"}
    assert DEFAULT_ALLOWED["cloudwatch"] == {"DescribeAlarms", "GetMetricData"}
    assert DEFAULT_ALLOWED["elbv2"] == {"DescribeLoadBalancers", "DescribeTargetGroups"}


def test_allowed_call_goes_through(session):
    logs = make_client(session, "logs", "us-east-1")
    with Stubber(logs) as stub:
        stub.add_response("filter_log_events", {"events": []}, {"logGroupName": "g"})
        assert logs.filter_log_events(logGroupName="g")["events"] == []


def test_another_services_read_op_is_refused_on_this_client(session):
    """Per-service: a logs client may not call an operation only cloudwatch needs."""
    logs = make_client(session, "logs", "us-east-1")
    with pytest.raises(ReadOnlyViolation, match="logs:DescribeLogGroups"):
        logs.describe_log_groups()


def test_refused_before_the_stubber_answers(session):
    """provide-client-params fires before any Stubber or parameter handler: the queued
    response stays unconsumed, so the call never got as far as being built."""
    logs = make_client(session, "logs", "us-east-1")
    stub = Stubber(logs)
    stub.add_response("delete_log_group", {}, {"logGroupName": "g"})
    stub.activate()
    with pytest.raises(ReadOnlyViolation):
        logs.delete_log_group(logGroupName="g")
    with pytest.raises(AssertionError):
        stub.assert_no_pending_responses()


def test_guard_runs_first_on_provide_client_params(session):
    assert awsguard.GUARD_EVENTS == ("provide-client-params", "before-parameter-build")
    logs = make_client(session, "logs", "us-east-1")
    calls = []
    logs.meta.events.register("provide-client-params", lambda **kw: calls.append("after"))
    logs.meta.events.register("before-parameter-build", lambda **kw: calls.append("build"))
    with pytest.raises(ReadOnlyViolation):
        logs.delete_log_group(logGroupName="g")
    assert calls == [], "the guard is registered first, so later handlers never run"


def test_second_event_still_guards_if_the_first_is_skipped(session):
    logs = make_client(session, "logs", "us-east-1")
    logs.meta.events.unregister("provide-client-params", unique_id="dawnfix-readonly-provide-client-params")
    with pytest.raises(ReadOnlyViolation):
        logs.delete_log_group(logGroupName="g")


def test_explicit_allowed_replaces_the_default(session):
    sts = make_client(session, "sts", None, allowed={"GetCallerIdentity"})
    with Stubber(sts) as stub:
        stub.add_response("get_caller_identity", {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/me", "UserId": "u"}, {})
        assert sts.get_caller_identity()["Account"] == "123456789012"
    with pytest.raises(ReadOnlyViolation):
        sts.assume_role(RoleArn="arn:aws:iam::123456789012:role/x", RoleSessionName="s")


def test_unknown_service_without_allowlist_refuses_everything(session):
    s3 = make_client(session, "s3", "us-east-1")
    with pytest.raises(ReadOnlyViolation):
        s3.list_buckets()


def test_empty_allowed_refuses_everything(session):
    logs = make_client(session, "logs", "us-east-1", allowed=())
    with pytest.raises(ReadOnlyViolation):
        logs.filter_log_events(logGroupName="g")


def test_a_string_is_not_an_allowlist(session):
    with pytest.raises(TypeError):
        make_client(session, "logs", "us-east-1", allowed="FilterLogEvents")


def test_clients_do_not_share_allowlists(session):
    a = make_client(session, "logs", "us-east-1", allowed={"DescribeLogGroups"})
    b = make_client(session, "logs", "us-east-1")
    with Stubber(a) as stub:
        stub.add_response("describe_log_groups", {"logGroups": []}, {})
        assert a.describe_log_groups()["logGroups"] == []
    with pytest.raises(ReadOnlyViolation):
        b.describe_log_groups()


def test_violation_names_the_refused_call(session):
    logs = make_client(session, "logs", "us-east-1")
    with pytest.raises(ReadOnlyViolation) as e:
        logs.delete_log_group(logGroupName="/x")
    assert (e.value.service, e.value.operation) == ("logs", "DeleteLogGroup")
    assert ReadOnlyViolation("plain").operation is None


def test_config_is_passed_through_and_the_guard_still_holds(session):
    from botocore.config import Config

    logs = make_client(session, "logs", "us-east-1", config=Config(user_agent_extra="probe/1"))
    assert "probe/1" in logs.meta.config.user_agent_extra
    with pytest.raises(ReadOnlyViolation):
        logs.delete_log_group(logGroupName="/x")
