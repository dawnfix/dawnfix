"""One scan end to end: list groups, read metrics, price, Insights (budgeted), suggest."""
import sys
import time
from datetime import datetime, timedelta, timezone

from dawnfix_core.sources.aws import ReadOnlyViolation

from . import brand
from .awsread import (INSIGHTS_OPERATIONS, READ_OPERATIONS, error_code, incoming, list_log_groups,
                      recent_query_count, subscription_filter_count)
from .insights import BudgetExceeded, plan_queries, run_plan
from .model import from_api, price_groups
from .prices import GB, Prices, usd
from .suggest import suggest


class ScanFailed(RuntimeError):
    pass


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def run_scan(*, make_client, regions: list[str], days: int, prices: Prices, now: datetime | None = None,
             top: int = 10, budget_gb: float = 5.0, hours: float = 24.0, retention_days: int = 30,
             confirm=None, log=_err, sleep=time.sleep) -> dict:
    """make_client(service, region, allowed_operations) -> boto3 client.
    confirm(prompt) -> bool is asked before any Logs Insights query; None means no."""
    now = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    now_ms = int(now.timestamp() * 1000)
    start = now - timedelta(days=days)
    notes, errors, groups = [], [], []

    account = None
    try:
        account = make_client("sts", regions[0], READ_OPERATIONS).get_caller_identity().get("Account")
    except ReadOnlyViolation:
        raise
    except Exception as e:
        notes.append(f"Account id not read ({error_code(e)}).")

    for region in regions:
        try:
            logs = make_client("logs", region, READ_OPERATIONS)
            found = [from_api(lg, region, prices) for lg in list_log_groups(logs)]
            for g in found:
                g.days = days
            if found:
                metrics = incoming(make_client("cloudwatch", region, READ_OPERATIONS),
                                   [g.name for g in found], start, now)
                for g in found:
                    m = metrics.get(g.name, {})
                    g.ingested_bytes = m.get("bytes", 0.0)
                    g.ingested_events = m.get("events", 0.0)
                    g.last_day_bytes = m.get("last_day_bytes", 0.0)
            groups.extend(found)
            log(f"{brand.CLI}: {region}: {len(found)} log groups")
        except ReadOnlyViolation:
            raise
        except Exception as e:
            errors.append({"region": region, "code": error_code(e)})
            log(f"{brand.CLI}: {region}: failed ({error_code(e)})")
    if errors and len(errors) == len(regions):
        raise ScanFailed(", ".join(f"{e['region']}: {e['code']}" for e in errors))

    price_groups(groups, prices)
    groups.sort(key=lambda g: g.monthly_usd, reverse=True)
    top_groups = [g for g in groups if g.monthly_usd > 0][:top]

    # Per-group detail that costs one call each: top groups only.
    for g in top_groups:
        logs = make_client("logs", g.region, READ_OPERATIONS)
        try:
            g.subscription_filters = subscription_filter_count(logs, g.name)
        except ReadOnlyViolation:
            raise
        except Exception as e:
            notes.append(f"Subscription filters of {g.name} not read ({error_code(e)}).")
        try:
            g.recent_queries = recent_query_count(logs, g.name)
        except ReadOnlyViolation:
            raise
        except Exception as e:
            notes.append(f"Recent Insights queries of {g.name} not read ({error_code(e)}).")

    insights = {"budget_gb": budget_gb, "planned_gb": 0.0, "est_usd": 0.0, "scanned_gb": 0.0,
                "usd": 0.0, "ran": False, "queries": [], "skipped": []}
    if budget_gb > 0 and top_groups:
        try:
            plan = plan_queries(top_groups, budget_gb, hours, now)
        except BudgetExceeded as e:  # cannot happen with plan_queries; kept as a hard stop
            plan = None
            notes.append(str(e))
        if plan and plan.items:
            est = plan.est_usd(prices)
            insights.update(planned_gb=plan.total_bytes / GB, est_usd=est,
                            skipped=[{"group": k, "reason": r} for k, r in plan.skipped])
            prompt = (f"Logs Insights will scan about {plan.total_bytes / GB:.2f} GB across "
                      f"{len(plan.items)} log group(s) (budget {budget_gb:g} GB), costing about {usd(est)}. Run it?")
            if confirm and confirm(prompt):
                res = run_plan(lambda r: make_client("logs", r, READ_OPERATIONS | INSIGHTS_OPERATIONS),
                               plan, sleep=sleep)
                scanned_usd = sum(q.get("bytes_scanned", 0) / GB * prices.insights_rate(q["group"].split(":", 1)[0])
                                  for q in res["queries"])
                insights.update(ran=True, queries=res["queries"], scanned_gb=res["scanned_bytes"] / GB,
                                usd=scanned_usd)
            else:
                notes.append("Logs Insights skipped: no confirmation (pass --yes to run it unattended). "
                             "Pattern-level savings are missing.")
        elif plan:
            insights["skipped"] = [{"group": k, "reason": r} for k, r in plan.skipped]
    elif budget_gb <= 0:
        notes.append("Logs Insights disabled (--insights-budget-gb 0). Pattern-level savings are missing.")

    suggestions, combined = suggest(groups, prices, now_ms, retention_days)
    total = sum(g.monthly_usd for g in groups)
    approx = sorted({g.region for g in groups if g.approx_price})
    if approx:
        notes.append(f"No prices for {', '.join(approx)}; used {prices.default_region} prices.")
    free_cap = prices.free_tier_gb * max((prices.ingest_rate(r, "STANDARD") for r in regions), default=0)
    return {
        "schema": brand.REPORT_SCHEMA,
        "product": brand.PRODUCT,
        "generated_at": now.isoformat(),
        "account": account,
        "regions": regions,
        "days": days,
        "retention_days": retention_days,
        "prices_source": prices.source(),
        "totals": {
            "groups": len(groups),
            "monthly_usd": total,
            "ingest_usd": sum(g.ingest_usd for g in groups),
            "storage_usd": sum(g.storage_usd for g in groups),
            "monthly_ingest_gb": sum(g.monthly_ingest_gb for g in groups),
            "stored_gb": sum(g.stored_bytes for g in groups) / GB,
            "never_expire": sum(1 for g in groups if g.never_expires),
            "savings_usd": min(combined, total),
            "free_tier_note": f"Before the AWS free tier ({prices.free_tier_gb:g} GB/month, worth at most {usd(free_cap)}).",
        },
        "groups": [g.to_dict() for g in groups],
        "top": [g.key for g in top_groups],
        "suggestions": [s.to_dict() for s in suggestions],
        "insights": insights,
        "errors": errors,
        "notes": notes,
        "pitch": {"product": brand.PITCH_PRODUCT, "line": brand.PITCH_LINE, "url": brand.PITCH_URL,
                  "install": brand.PITCH_INSTALL},
    }
