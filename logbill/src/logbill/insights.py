"""Logs Insights `pattern` queries on the costliest groups, inside a hard GB budget."""
import hashlib
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from dawnfix_core.redact import safe_redact

from .model import Group, Pattern
from .prices import GB, Prices

QUERY = "pattern @message | sort @sampleCount desc | limit 25"
MIN_WINDOW_HOURS = 0.25
TOKEN_LEN = 8          # assumed length of a dynamic <Token-n> when estimating line size
MAX_PATTERN_CHARS = 400
TOKEN_RX = re.compile(r"<[^<>\s]{1,60}>")


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class PlanItem:
    group: Group
    start: datetime
    end: datetime
    est_bytes: float

    @property
    def hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600


@dataclass
class Plan:
    items: list = field(default_factory=list)
    budget_bytes: float = 0.0
    skipped: list = field(default_factory=list)   # (group key, reason)

    @property
    def total_bytes(self) -> float:
        return sum(i.est_bytes for i in self.items)

    def est_usd(self, prices: Prices) -> float:
        return sum(i.est_bytes / GB * prices.insights_rate(i.group.region) for i in self.items)


def check_budget(plan: Plan) -> None:
    if plan.total_bytes > plan.budget_bytes * (1 + 1e-9):
        raise BudgetExceeded(
            f"planned Logs Insights scan {plan.total_bytes / GB:.2f} GB exceeds the "
            f"--insights-budget-gb {plan.budget_bytes / GB:.2f} GB")


def plan_queries(groups: list[Group], budget_gb: float, hours: float, end: datetime) -> Plan:
    """Walk the groups (costliest first) and give each the window `hours`, shrunk to
    what is left of the budget. A group that cannot get MIN_WINDOW_HOURS is skipped."""
    plan = Plan(budget_bytes=max(budget_gb, 0.0) * GB)
    left = plan.budget_bytes
    for g in groups:
        rate = g.bytes_per_hour()
        if g.log_class == "DELIVERY":
            plan.skipped.append((g.key, "delivery class"))
            continue
        if rate <= 0:
            plan.skipped.append((g.key, "no ingestion"))
            continue
        h = min(hours, left / rate)
        if h < MIN_WINDOW_HOURS:
            plan.skipped.append((g.key, "budget"))
            continue
        h = int(h * 60) / 60  # whole minutes, rounded down so the estimate stays inside
        est = rate * h
        plan.items.append(PlanItem(g, end - timedelta(hours=h), end, est))
        left -= est
    check_budget(plan)
    return plan


def pattern_id(region: str, group: str, text: str) -> str:
    return hashlib.sha256(f"{region}\0{group}\0{text}".encode()).hexdigest()[:12]


def _est_len(text: str) -> int:
    return max(len(TOKEN_RX.sub("x" * TOKEN_LEN, text)), 1)


def parse_results(rows: list, group: Group) -> list[Pattern]:
    """Rows from GetQueryResults -> redacted patterns with an estimated byte share.

    `pattern` gives counts, not bytes. A pattern's bytes are estimated as
    count x its length (tokens counted as TOKEN_LEN chars), scaled so the mean line
    size matches the window's bytes per event; the shares of the returned patterns
    then add up to the share of events they cover."""
    pats = []
    for row in rows:
        f = {c.get("field"): c.get("value") for c in row if isinstance(c, dict)}
        text = f.get("@pattern")
        if not text:
            continue
        try:
            count = int(float(f.get("@sampleCount") or 0))
            ratio = float(f.get("@ratio") or 0)
        except ValueError:
            continue
        red = safe_redact(text)[:MAX_PATTERN_CHARS]
        pats.append(Pattern(id=pattern_id(group.region, group.name, red), text=red, count=count,
                            ratio=ratio, severity=safe_redact(f.get("@severityLabel") or "")[:20]))
    if not pats:
        return pats
    events = [p.count / p.ratio for p in pats if p.ratio > 0]
    total_events = max(events) if events else sum(p.count for p in pats)
    counted = sum(p.count for p in pats)
    mean_len = sum(p.count * _est_len(p.text) for p in pats) / counted if counted else 1
    for p in pats:
        share = (p.count / total_events) * (_est_len(p.text) / mean_len) if total_events else 0.0
        p.byte_share = min(share, 1.0)
        p.monthly_usd = p.byte_share * group.ingest_usd
    pats.sort(key=lambda p: p.monthly_usd, reverse=True)
    return pats


def run_plan(make_logs_client, plan: Plan, sleep=time.sleep, timeout_s: float = 300,
             poll_s: float = 2.0) -> dict:
    """Runs the plan's queries one at a time. Before each query the estimate must fit
    in what is left of the budget after the bytes already scanned (as AWS reports
    them); after the budget is used up no further query starts."""
    check_budget(plan)
    scanned = 0.0
    out = {"queries": [], "scanned_bytes": 0.0}
    for item in plan.items:
        g = item.group
        if scanned + item.est_bytes > plan.budget_bytes:
            out["queries"].append({"group": g.key, "status": "skipped_budget"})
            continue
        logs = make_logs_client(g.region)
        qid = logs.start_query(
            logGroupNames=[g.name], startTime=int(item.start.timestamp()), endTime=int(item.end.timestamp()),
            queryString=QUERY, limit=25,
        )["queryId"]
        waited, resp = 0.0, {}
        while True:
            resp = logs.get_query_results(queryId=qid)
            status = resp.get("status")
            if status in ("Complete", "Failed", "Cancelled", "Timeout", "Unknown"):
                break
            if waited >= timeout_s:
                logs.stop_query(queryId=qid)
                status = "StoppedByLogbill"
                break
            sleep(poll_s)
            waited += poll_s
        stats = resp.get("statistics", {}) or {}
        b = float(stats.get("bytesScanned") or 0.0)
        scanned += b
        g.insights = {"window_hours": round(item.hours, 2), "est_bytes": item.est_bytes, "bytes_scanned": b,
                      "status": status}
        if status == "Complete":
            g.patterns = parse_results(resp.get("results", []), g)
        out["queries"].append({"group": g.key, "status": status, "bytes_scanned": b,
                               "est_bytes": item.est_bytes, "window_hours": round(item.hours, 2)})
    out["scanned_bytes"] = scanned
    return out
