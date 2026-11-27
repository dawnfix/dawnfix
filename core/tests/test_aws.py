import json
from datetime import timedelta

import boto3
import pytest
from botocore.stub import ANY, Stubber

from dawnfix_core.config import AwsSourceConfig, LogGroup
from dawnfix_core.sources import SourceError, Window
from dawnfix_core.sources.aws import DEFAULT_FILTER, AwsSource, ReadOnlyViolation, make_client
from tests.conftest import NOW

WINDOW = Window(NOW - timedelta(minutes=60), NOW)
LIMITS = {"max_events_per_source": 5000}
LB_ARN = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-lb/50dc6c495c0c9188"
TG_ARN = "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/my-api-tg/73e2d6bc24d8a067"


@pytest.fixture
def session():
    return boto3.session.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name="us-east-1")


def stubbed(session, *services):
    clients, stubs = {}, {}
    for s in services:
        clients[s] = make_client(session, s, "us-east-1")
        stubs[s] = Stubber(clients[s])
        stubs[s].activate()
    return clients, stubs


def src(clients, limits=LIMITS, **conf):
    c = AwsSourceConfig(region="us-east-1", **conf)
    return AwsSource(c, limits, clients=clients)


def msg(i):
    return json.dumps({"level": 50, "req": {"method": "GET", "url": f"/users/{i}"}, "res": {"statusCode": 500},
                       "err": {"type": "TypeError", "message": "x is undefined"}})


def test_logs_paginated_and_filtered(session):
    clients, stubs = stubbed(session, "logs")
    expected = {"logGroupName": "my-api-prod", "startTime": int(WINDOW.start.timestamp() * 1000),
                "endTime": int(WINDOW.end.timestamp() * 1000), "filterPattern": DEFAULT_FILTER}
    stubs["logs"].add_response("filter_log_events", {
        "events": [{"message": msg(1), "timestamp": 1761559200000},
                   {"message": json.dumps({"level": 30, "msg": "fine"}), "timestamp": 1761559200000}],
        "nextToken": "t1"}, expected)
    stubs["logs"].add_response("filter_log_events", {"events": [{"message": msg(2), "timestamp": 1761559300000}]},
                               {**expected, "nextToken": "t1"})
    evs = src(clients, log_groups=[LogGroup("my-api-prod")]).events(WINDOW)
    stubs["logs"].assert_no_pending_responses()
    assert len(evs) == 2  # the info line is dropped
    assert {e.route for e in evs} == {"/users/:id"}
    assert len({e.fingerprint for e in evs}) == 1
    assert evs[0].status == 500 and evs[0].error_class == "TypeError" and evs[0].service == "my-api-prod"


def test_logs_capped(session):
    clients, stubs = stubbed(session, "logs")
    stubs["logs"].add_response("filter_log_events",
                               {"events": [{"message": msg(i), "timestamp": 1} for i in range(5)], "nextToken": "more"},
                               {"logGroupName": "g", "startTime": ANY, "endTime": ANY, "filterPattern": "ERROR",
                                "logStreamNamePrefix": "cron"})
    s = src(clients, limits={"max_events_per_source": 3},
            log_groups=[LogGroup("g", filter_pattern="ERROR", stream_prefix="cron"), LogGroup("h")])
    evs = s.events(WINDOW)
    assert len(evs) == 3 and s.truncated


def test_alarms(session):
    clients, stubs = stubbed(session, "cloudwatch")
    stubs["cloudwatch"].add_response(
        "describe_alarms",
        {"MetricAlarms": [{"AlarmName": "my-api-prod-5xx-high", "StateReason": "Threshold Crossed: 1 datapoint [12.0]",
                           "StateUpdatedTimestamp": NOW}],
         "CompositeAlarms": [], "NextToken": "n"},
        {"StateValue": "ALARM", "AlarmTypes": ["MetricAlarm", "CompositeAlarm"]})
    stubs["cloudwatch"].add_response(
        "describe_alarms",
        {"MetricAlarms": [{"AlarmName": "my-api-prod-AlarmLow-scale-in", "StateUpdatedTimestamp": NOW}]},
        {"StateValue": "ALARM", "AlarmTypes": ["MetricAlarm", "CompositeAlarm"], "NextToken": "n"})
    evs = src(clients, alarms=True).events(WINDOW)
    assert [e.alarm for e in evs] == ["my-api-prod-5xx-high", "my-api-prod-AlarmLow-scale-in"]
    assert all(e.kind == "alarm" and e.stem == "ALARM" for e in evs)


def test_alb_metrics(session):
    clients, stubs = stubbed(session, "elbv2", "cloudwatch")
    other = LB_ARN.replace("app/my-lb/", "app/other-lb/")
    stubs["elbv2"].add_response("describe_load_balancers",
                                {"LoadBalancers": [{"LoadBalancerArn": LB_ARN}, {"LoadBalancerArn": other}]}, {})
    stubs["elbv2"].add_response("describe_target_groups", {"TargetGroups": [{"TargetGroupArn": TG_ARN}]},
                                {"LoadBalancerArn": LB_ARN})
    stubs["cloudwatch"].add_response("get_metric_data", {"MetricDataResults": [
        {"Id": "q0", "Values": [2.0, 1.0]},  # ELB 502
        {"Id": "q1", "Values": []},
        {"Id": "q2", "Values": [0.0]},
        {"Id": "q3", "Values": [4.0, 3.0]},  # target 5xx
    ]}, {"MetricDataQueries": ANY, "StartTime": WINDOW.start, "EndTime": WINDOW.end})
    evs = src(clients, alb="app/my-lb/*").events(WINDOW)
    got = {(e.service, e.error_class, e.count) for e in evs}
    assert got == {("my-lb", "ELB502", 3), ("my-lb/my-api-tg", "Target5XX", 7)}


def test_client_error_becomes_code_only(session):
    clients, stubs = stubbed(session, "logs")
    stubs["logs"].add_client_error("filter_log_events", service_error_code="ExpiredTokenException",
                                   service_message="token for jane@example.com expired")
    with pytest.raises(SourceError) as e:
        src(clients, log_groups=[LogGroup("g")]).events(WINDOW)
    assert e.value.code == "ExpiredTokenException"
    assert "jane" not in str(e.value)


def test_write_calls_are_refused(session):
    clients, stubs = stubbed(session, "logs")
    stubs["logs"].add_response("delete_log_group", {}, {"logGroupName": "g"})
    with pytest.raises(ReadOnlyViolation):
        clients["logs"].delete_log_group(logGroupName="g")
