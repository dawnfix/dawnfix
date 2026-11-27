"""AWS calls. Every client refuses any operation outside its allowlist before the
request is built (the same guard as dawnfix_core.sources.aws)."""
from datetime import datetime

from dawnfix_core.sources.aws import ReadOnlyViolation

from . import brand

# The scan: metadata and metrics only. Free or near free.
READ_OPERATIONS = frozenset({
    "DescribeLogGroups",
    "DescribeSubscriptionFilters",
    "DescribeQueries",
    "GetMetricData",
    "GetCallerIdentity",
})
# Logs Insights: read-only on the data, but billed per GB scanned. Only on a
# client built after the budget check and the user's yes.
INSIGHTS_OPERATIONS = frozenset({"StartQuery", "GetQueryResults", "StopQuery"})
# The one write logbill can make, from `logbill fix --apply` after a typed confirmation.
WRITE_OPERATIONS = frozenset({"PutRetentionPolicy"})

MAX_PAGES = 500
METRIC_QUERIES_PER_CALL = 500


def _guard_for(allowed: frozenset):
    def guard(model=None, **_):
        if model is not None and model.name not in allowed:
            raise ReadOnlyViolation(f"{brand.CLI} refused AWS call {model.name} (not in this client's allowlist)")
    return guard


def make_client(session, service: str, region: str | None, allowed: frozenset = READ_OPERATIONS):
    client = session.client(service, region_name=region)
    client.meta.events.register_first("before-parameter-build", _guard_for(frozenset(allowed)))
    return client


def error_code(e: Exception) -> str:
    resp = getattr(e, "response", None)
    if isinstance(resp, dict):
        return resp.get("Error", {}).get("Code") or type(e).__name__
    return type(e).__name__


def list_log_groups(logs) -> list[dict]:
    out, params = [], {}
    for _ in range(MAX_PAGES):
        resp = logs.describe_log_groups(**params)
        out.extend(resp.get("logGroups", []))
        token = resp.get("nextToken")
        if not token or token == params.get("nextToken"):
            break
        params["nextToken"] = token
    return out


def _metric(name: str, group: str) -> dict:
    return {
        "MetricStat": {
            "Metric": {"Namespace": "AWS/Logs", "MetricName": name,
                       "Dimensions": [{"Name": "LogGroupName", "Value": group}]},
            "Period": 86400,
            "Stat": "Sum",
        },
        "ReturnData": True,
    }


def incoming(cw, names: list[str], start: datetime, end: datetime) -> dict[str, dict]:
    """Per group: total IncomingBytes and IncomingLogEvents over [start, end) in
    daily buckets, plus the newest day's bytes (for the Insights scan estimate)."""
    out = {n: {"bytes": 0.0, "events": 0.0, "last_day_bytes": 0.0} for n in names}
    per_call = METRIC_QUERIES_PER_CALL // 2
    for base in range(0, len(names), per_call):
        chunk = names[base:base + per_call]
        ids = {}
        mdq = []
        for i, n in enumerate(chunk):
            for kind, metric in (("b", "IncomingBytes"), ("e", "IncomingLogEvents")):
                qid = f"{kind}{base + i}"
                ids[qid] = (n, kind)
                mdq.append(dict(_metric(metric, n), Id=qid))
        params = {"MetricDataQueries": mdq, "StartTime": start, "EndTime": end,
                  "ScanBy": "TimestampDescending"}
        seen_latest = set()
        for _ in range(MAX_PAGES):
            resp = cw.get_metric_data(**params)
            for r in resp.get("MetricDataResults", []):
                if r.get("Id") not in ids:
                    continue
                n, kind = ids[r["Id"]]
                vals = r.get("Values", [])
                if kind == "b":
                    out[n]["bytes"] += sum(vals)
                    if vals and r["Id"] not in seen_latest:  # newest first, first page only
                        out[n]["last_day_bytes"] = vals[0]
                        seen_latest.add(r["Id"])
                else:
                    out[n]["events"] += sum(vals)
            token = resp.get("NextToken")
            if not token or token == params.get("NextToken"):
                break
            params["NextToken"] = token
    return out


def subscription_filter_count(logs, name: str) -> int:
    n, params = 0, {"logGroupName": name}
    for _ in range(MAX_PAGES):
        resp = logs.describe_subscription_filters(**params)
        n += len(resp.get("subscriptionFilters", []))
        token = resp.get("nextToken")
        if not token or token == params.get("nextToken"):
            break
        params["nextToken"] = token
    return n


def recent_query_count(logs, name: str) -> int:
    """Logs Insights queries AWS still lists for this group (recent history only)."""
    n, params = 0, {"logGroupName": name, "maxResults": 1000}
    for _ in range(20):
        resp = logs.describe_queries(**params)
        n += len(resp.get("queries", []))
        token = resp.get("nextToken")
        if not token or token == params.get("nextToken"):
            break
        params["nextToken"] = token
    return n
