"""AWS: CloudWatch Logs, alarms in ALARM, ALB 5xx metrics. Read-only by construction."""
import fnmatch
from datetime import datetime, timezone

from ..awsguard import DEFAULT_ALLOWED, READ_ONLY_OPERATIONS, ReadOnlyViolation, make_client
from ..normalize import Event, parse_log_message, service_name
from . import SourceError, Window

# The guard lives in dawnfix_core.awsguard (public: make_client, ReadOnlyViolation, the
# per-service DEFAULT_ALLOWED); these names stay importable from here for older callers.
__all__ = ["AwsSource", "DEFAULT_ALLOWED", "DEFAULT_FILTER", "READ_ONLY_OPERATIONS",
           "ReadOnlyViolation", "make_client"]

MAX_PAGES = 200
# Broad enough for JSON (pino/bunyan levels, 5xx statuses) and text logs; per group override.
DEFAULT_FILTER = (
    '?ERROR ?Error ?error ?FATAL ?Exception ?Traceback '
    '?"\\"level\\":50" ?"\\"level\\":60" ?"\\"statusCode\\":5" ?"\\"status\\":5" ?" 500 " ?" 502 " ?" 503 " ?" 504 "'
)
ALB_METRICS = [
    ("HTTPCode_ELB_502_Count", 502),
    ("HTTPCode_ELB_503_Count", 503),
    ("HTTPCode_ELB_504_Count", 504),
]


def _code(e: Exception) -> str:
    resp = getattr(e, "response", None)
    if isinstance(resp, dict):
        return resp.get("Error", {}).get("Code") or type(e).__name__
    return type(e).__name__


class AwsSource:
    type = "aws"

    def __init__(self, conf, limits: dict, session=None, clients: dict | None = None):
        self.conf = conf
        self.cap = int(limits.get("max_events_per_source", 5000))
        self._session = session
        self._clients = dict(clients or {})
        self.truncated = False

    @property
    def id(self) -> str:
        return self.conf.id

    def client(self, service: str):
        if service not in self._clients:
            if self._session is None:
                import boto3

                # Credentials come from the environment: in CI, the OIDC role the
                # workflow assumed (conf.role) via aws-actions/configure-aws-credentials.
                self._session = boto3.session.Session()
            self._clients[service] = make_client(self._session, service, self.conf.region)
        return self._clients[service]

    def events(self, window: Window) -> list[Event]:
        try:
            out = []
            for g in self.conf.log_groups:
                out.extend(self._logs(g, window, self.cap - len(out)))
            if self.conf.alarms:
                out.extend(self._alarms())
            if self.conf.alb:
                out.extend(self._alb(window))
            return out
        except ReadOnlyViolation:
            raise
        except Exception as e:  # botocore errors carry a code; messages may echo input, so drop them
            raise SourceError(_code(e)) from None

    def _logs(self, group, window: Window, budget: int) -> list[Event]:
        if budget <= 0:
            self.truncated = True
            return []
        params = {
            "logGroupName": group.name,
            "startTime": int(window.start.timestamp() * 1000),
            "endTime": int(window.end.timestamp() * 1000),
        }
        pattern = group.filter_pattern if group.filter_pattern is not None else DEFAULT_FILTER
        if pattern:
            params["filterPattern"] = pattern
        if group.stream_prefix:
            params["logStreamNamePrefix"] = group.stream_prefix
        logs = self.client("logs")
        service = service_name(group.name)
        out = []
        for _ in range(MAX_PAGES):
            resp = logs.filter_log_events(**params)
            for ev in resp.get("events", []):
                p = parse_log_message(ev.get("message", ""))
                if not p["is_error"]:
                    continue
                out.append(Event(
                    source="aws", source_id=self.id, kind="log", service=service,
                    route=p["route"], method=p["method"], status=p["status"],
                    error_class=p["error_class"], message=p["message"],
                    timestamp=_ms(ev.get("timestamp")),
                ))
                if len(out) >= budget:
                    self.truncated = True
                    return out
            token = resp.get("nextToken")
            if not token or token == params.get("nextToken"):
                break
            params["nextToken"] = token
        return out

    def _alarms(self) -> list[Event]:
        cw = self.client("cloudwatch")
        params = {"StateValue": "ALARM", "AlarmTypes": ["MetricAlarm", "CompositeAlarm"]}
        out = []
        for _ in range(MAX_PAGES):
            resp = cw.describe_alarms(**params)
            for a in resp.get("MetricAlarms", []) + resp.get("CompositeAlarms", []):
                name = a.get("AlarmName", "")
                out.append(Event(
                    source="aws", source_id=self.id, kind="alarm", service=service_name(name),
                    alarm=name, error_class="Alarm", stem="ALARM",
                    message=a.get("StateReason", ""), timestamp=a.get("StateUpdatedTimestamp"),
                ))
            token = resp.get("NextToken")
            if not token:
                break
            params["NextToken"] = token
        return out

    def _load_balancers(self) -> list[tuple[str, str]]:
        """(arn, dimension value 'app/<name>/<id>') for balancers matching conf.alb."""
        elb = self.client("elbv2")
        params, found = {}, []
        for _ in range(MAX_PAGES):
            resp = elb.describe_load_balancers(**params)
            for lb in resp.get("LoadBalancers", []):
                arn = lb["LoadBalancerArn"]
                dim = arn.split(":loadbalancer/", 1)[-1]
                if fnmatch.fnmatchcase(dim, self.conf.alb):
                    found.append((arn, dim))
            token = resp.get("NextMarker")
            if not token:
                break
            params["Marker"] = token
        return found

    def _alb(self, window: Window) -> list[Event]:
        elb = self.client("elbv2")
        queries = []  # (query, service, error_class, stem, status)
        for arn, lb_dim in self._load_balancers():
            lb_name = lb_dim.split("/")[1]
            lb_d = {"Name": "LoadBalancer", "Value": lb_dim}
            for metric, status in ALB_METRICS:
                queries.append((_metric(metric, [lb_d]), lb_name, f"ELB{status}", metric, status))
            tgs = elb.describe_target_groups(LoadBalancerArn=arn).get("TargetGroups", [])
            for tg in tgs:
                tg_dim = tg["TargetGroupArn"].split(":", 5)[-1]  # targetgroup/<name>/<id>
                tg_name = tg_dim.split("/")[1] if "/" in tg_dim else tg_dim
                queries.append((
                    _metric("HTTPCode_Target_5XX_Count", [lb_d, {"Name": "TargetGroup", "Value": tg_dim}]),
                    f"{lb_name}/{tg_name}", "Target5XX", "HTTPCode_Target_5XX_Count", 500,
                ))
        if not queries:
            return []
        totals = {}
        cw = self.client("cloudwatch")
        for start in range(0, len(queries), 500):
            batch = queries[start:start + 500]
            mdq = [dict(q[0], Id=f"q{start + i}") for i, q in enumerate(batch)]
            params = {"MetricDataQueries": mdq, "StartTime": window.start, "EndTime": window.end}
            for _ in range(MAX_PAGES):
                resp = cw.get_metric_data(**params)
                for r in resp.get("MetricDataResults", []):
                    totals[r["Id"]] = totals.get(r["Id"], 0) + sum(r.get("Values", []))
                token = resp.get("NextToken")
                if not token:
                    break
                params["NextToken"] = token
        out = []
        for i, (_, service, cls, stem, status) in enumerate(queries):
            n = int(round(totals.get(f"q{i}", 0)))
            if n > 0:
                out.append(Event(
                    source="aws", source_id=self.id, kind="alb", service=service_name(service),
                    status=status, error_class=cls, stem=stem, count=n, timestamp=window.end,
                ))
        return out


def _metric(name: str, dims: list) -> dict:
    return {
        "MetricStat": {
            "Metric": {"Namespace": "AWS/ApplicationELB", "MetricName": name, "Dimensions": dims},
            "Period": 60,
            "Stat": "Sum",
        },
        "ReturnData": True,
    }


def _ms(ts):
    if ts is None:
        return None
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
