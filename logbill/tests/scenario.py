"""A small fake account: three log groups, metrics, two Insights queries."""
from datetime import timedelta

from logbill.awsread import INSIGHTS_OPERATIONS, READ_OPERATIONS
from logbill.prices import GB
from logbill.scan import run_scan
from tests.conftest import DAY_MS, NOW, NOW_MS

INS = READ_OPERATIONS | INSIGHTS_OPERATIONS
EMAIL = "jane.doe@example.com"

GROUPS = [
    {"logGroupName": "/ecs/api-prod", "storedBytes": 500 * GB, "creationTime": NOW_MS - 1000 * DAY_MS,
     "metricFilterCount": 0, "logGroupClass": "STANDARD"},
    {"logGroupName": "/aws/lambda/checkout-prod", "storedBytes": 5 * GB, "creationTime": NOW_MS - 400 * DAY_MS,
     "retentionInDays": 14, "metricFilterCount": 1, "logGroupClass": "STANDARD"},
    {"logGroupName": "/app/kept-staging", "storedBytes": 1 * GB, "creationTime": NOW_MS - 90 * DAY_MS,
     "retentionInDays": 30, "metricFilterCount": 0, "logGroupClass": "STANDARD"},
]


def _res(qid, values):
    return {"Id": qid, "Label": qid, "StatusCode": "Complete", "Values": values,
            "Timestamps": [NOW - timedelta(days=i) for i in range(len(values))]}


def _row(pattern, count, ratio, sev="Info"):
    return [{"field": "@pattern", "value": pattern}, {"field": "@sampleCount", "value": str(count)},
            {"field": "@ratio", "value": str(ratio)}, {"field": "@severityLabel", "value": sev}]


API_ROWS = [
    _row('{"level":"debug","msg":"cache lookup for order <Number-1> took <Number-2> ms"}', 5000, 0.5, "Debug"),
    _row(f"order accepted, sending confirmation to {EMAIL}", 2000, 0.2),
    _row("<script>alert(1)</script> request done", 1000, 0.1),
]
LAMBDA_ROWS = [
    _row("START RequestId: <UUID-1> Version: $LATEST", 3000, 0.3),
    _row("REPORT RequestId: <UUID-1> Duration: <Number-2> ms Billed Duration: <Number-3> ms", 3000, 0.3),
]


def stub_account(factory, insights=True):
    factory.stub("sts").add_response("get_caller_identity", {
        "UserId": "AIDA", "Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/x"})
    logs = factory.stub("logs")
    logs.add_response("describe_log_groups", {"logGroups": GROUPS})
    # 2 GB/day for the API, 1 GB/day for the Lambda, nothing for staging
    factory.stub("cloudwatch").add_response("get_metric_data", {"MetricDataResults": [
        _res("b0", [2 * GB] * 30), _res("e0", [1e6] * 30), _res("b1", [1 * GB] * 30), _res("e1", [5e5] * 30),
        _res("b2", []), _res("e2", [])]})
    # top groups by cost: api, lambda, staging (storage only)
    for _ in range(3):
        logs.add_response("describe_subscription_filters", {"subscriptionFilters": []})
        logs.add_response("describe_queries", {"queries": []})
    if insights:
        ins = factory.stub("logs", allowed=INS)
        for qid, rows in (("q1", API_ROWS), ("q2", LAMBDA_ROWS)):
            ins.add_response("start_query", {"queryId": qid})
            ins.add_response("get_query_results", {
                "status": "Complete", "results": rows,
                "statistics": {"bytesScanned": 1.5 * GB, "recordsMatched": 1, "recordsScanned": 1}},
                {"queryId": qid})


def scan(factory, prices, confirm=lambda p: True, **kw):
    kw.setdefault("budget_gb", 5)
    return run_scan(make_client=factory, regions=["us-east-1"], days=30, prices=prices, now=NOW,
                    confirm=confirm, log=lambda m: None, **kw)
