from datetime import timedelta

import pytest

from logbill.awsread import incoming, list_log_groups
from tests.conftest import NOW


def _res(qid, values):
    return {"Id": qid, "Label": qid, "StatusCode": "Complete", "Values": values,
            "Timestamps": [NOW - timedelta(days=i) for i in range(len(values))]}


def test_incoming_bytes_are_summed_per_group_across_pages(factory):
    cw = factory("cloudwatch", "us-east-1")
    stub = factory.stub("cloudwatch")
    start = NOW - timedelta(days=30)
    stub.add_response("get_metric_data", {
        "MetricDataResults": [_res("b0", [300.0, 100.0]), _res("e0", [3.0, 1.0]), _res("b1", [50.0])],
        "NextToken": "p2"})
    stub.add_response("get_metric_data", {
        "MetricDataResults": [_res("b0", [10.0]), _res("e1", [5.0])]})
    out = incoming(cw, ["/app/a", "/app/b"], start, NOW)
    stub.assert_no_pending_responses()
    assert out["/app/a"] == {"bytes": 410.0, "events": 4.0, "last_day_bytes": 300.0}
    assert out["/app/b"] == {"bytes": 50.0, "events": 5.0, "last_day_bytes": 50.0}


def test_metric_queries_name_the_log_group_dimension(factory):
    cw = factory("cloudwatch", "us-east-1")
    stub = factory.stub("cloudwatch")
    seen = {}

    def capture(params, **_):
        seen.update(params)
    cw.meta.events.register("provide-client-params.cloudwatch.GetMetricData", capture)
    stub.add_response("get_metric_data", {"MetricDataResults": []})
    incoming(cw, ["/app/a"], NOW - timedelta(days=1), NOW)
    q = {m["Id"]: m["MetricStat"] for m in seen["MetricDataQueries"]}
    assert q["b0"]["Metric"] == {"Namespace": "AWS/Logs", "MetricName": "IncomingBytes",
                                 "Dimensions": [{"Name": "LogGroupName", "Value": "/app/a"}]}
    assert q["e0"]["Metric"]["MetricName"] == "IncomingLogEvents"
    assert q["b0"]["Period"] == 86400 and q["b0"]["Stat"] == "Sum"


def test_many_groups_are_batched_under_500_queries(factory):
    cw = factory("cloudwatch", "us-east-1")
    stub = factory.stub("cloudwatch")
    names = [f"/g/{i}" for i in range(260)]  # 520 queries -> 2 calls
    stub.add_response("get_metric_data", {"MetricDataResults": [_res("b0", [1.0])]})
    stub.add_response("get_metric_data", {"MetricDataResults": [_res("b259", [2.0])]})
    out = incoming(cw, names, NOW - timedelta(days=1), NOW)
    stub.assert_no_pending_responses()
    assert out["/g/0"]["bytes"] == 1.0 and out["/g/259"]["bytes"] == 2.0


def test_list_log_groups_paginates(factory):
    logs = factory("logs", "us-east-1")
    stub = factory.stub("logs")
    stub.add_response("describe_log_groups", {"logGroups": [{"logGroupName": "a"}], "nextToken": "t"})
    stub.add_response("describe_log_groups", {"logGroups": [{"logGroupName": "b"}]}, {"nextToken": "t"})
    assert [g["logGroupName"] for g in list_log_groups(logs)] == ["a", "b"]


@pytest.mark.parametrize("op", ["put_retention_policy", "delete_log_group", "start_query"])
def test_read_client_refuses_writes_and_insights(factory, op):
    from dawnfix_core.sources.aws import ReadOnlyViolation

    logs = factory("logs", "us-east-1")
    # Queue a response so the Stubber lets the call through: the guard must be what refuses it.
    factory.stub("logs").add_response(op, {})
    args = {"put_retention_policy": {"logGroupName": "a", "retentionInDays": 30},
            "delete_log_group": {"logGroupName": "a"},
            "start_query": {"logGroupName": "a", "startTime": 0, "endTime": 1, "queryString": "x"}}[op]
    with pytest.raises(ReadOnlyViolation):
        getattr(logs, op)(**args)
