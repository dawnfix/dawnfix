"""Savings suggestions with a $/month figure each, and a total that never counts the
same dollar twice."""
import re
import shlex
from dataclasses import asdict, dataclass, field

from .model import Group
from .prices import GB, Prices

RETENTION_CHOICES = (30, 90)
NOISY_SHARE = 0.05        # a pattern worth flagging: >= 5% of the group's bytes ...
NOISY_MIN_USD = 1.0       # ... or >= $1/month
LOW_QUERY_MAX = 2         # recent Insights queries at or below this count as "rarely queried"
MIN_USD = 0.01

LAMBDA_PLATFORM = re.compile(r"^\s*(START|END|REPORT|INIT_START)\s+(RequestId|Runtime|Duration)\b")
DEBUG = re.compile(r"\b(DEBUG|TRACE)\b|\"?level\"?\s*[:=]\s*\"?(debug|trace|10|20)\b|\blevel=(debug|trace)\b", re.I)
NON_PROD = re.compile(r"(^|[-_/.])(dev|develop|development|test|testing|qa|staging|stage|stg|sandbox|local)([-_/.]|$)", re.I)
CONTAINER_INSIGHTS = re.compile(r"^/aws/(ecs/)?containerinsights/.+/performance$")


@dataclass
class Suggestion:
    kind: str
    region: str
    group: str
    title: str
    detail: str
    monthly_usd: float
    pattern_ids: list = field(default_factory=list)
    command: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def projected_stored_bytes(g: Group, days: int, now_ms: int) -> float:
    """Steady-state stored bytes under `days` retention, assuming the group's
    stored bytes accumulated evenly over its age."""
    age = g.age_days(now_ms)
    if age is None:
        return float(g.stored_bytes)
    return g.stored_bytes * min(1.0, days / age)


def retention_saving(g: Group, days: int, now_ms: int, prices: Prices) -> float:
    if not g.never_expires:
        return 0.0
    drop = g.stored_bytes - projected_stored_bytes(g, days, now_ms)
    return max(drop, 0.0) / GB * prices.storage_rate(g.region)


def ia_eligible(g: Group) -> tuple[bool, str]:
    if g.log_class != "STANDARD":
        return False, "not Standard class"
    if g.metric_filters:
        return False, "has metric filters (Infrequent Access has none)"
    if g.subscription_filters is None:
        return False, "subscription filters not checked"
    if g.subscription_filters:
        return False, "has subscription filters (Infrequent Access has none)"
    if g.recent_queries is not None and g.recent_queries > LOW_QUERY_MAX:
        return False, "queried often"
    return True, ""


def ia_saving(g: Group, prices: Prices, ingest_usd: float | None = None) -> float:
    base = g.ingest_usd if ingest_usd is None else ingest_usd
    std = prices.ingest_rate(g.region, "STANDARD")
    ia = prices.ingest_rate(g.region, "INFREQUENT_ACCESS")
    return base * (1 - ia / std) if std else 0.0


def is_prod_like(name: str) -> bool:
    return not NON_PROD.search(name)


def _cmd(*args) -> str:
    return " ".join(shlex.quote(a) for a in args)


def suggest(groups: list[Group], prices: Prices, now_ms: int, retention_days: int = 30) -> tuple[list, float]:
    """(suggestions sorted by $, combined monthly saving)."""
    out: list[Suggestion] = []
    combined = 0.0
    for g in groups:
        storage_save = 0.0
        if g.never_expires and g.stored_bytes:
            for days in sorted(set(RETENTION_CHOICES) | {retention_days}):
                s = retention_saving(g, days, now_ms, prices)
                if s >= MIN_USD:
                    out.append(Suggestion(
                        "retention", g.region, g.name, f"Set {days}-day retention (never expires today)",
                        f"Stores {g.stored_bytes / GB:,.1f} GB with no expiry. At {days} days about "
                        f"{projected_stored_bytes(g, days, now_ms) / GB:,.1f} GB would remain.",
                        s, command=_cmd("aws", "logs", "put-retention-policy", "--region", g.region,
                                        "--log-group-name", g.name, "--retention-in-days", str(days))))
            storage_save = retention_saving(g, retention_days, now_ms, prices)

        # Ingestion: patterns to drop, then Infrequent Access on what is left.
        dropped: dict[str, float] = {}
        lambda_ids, lambda_usd, debug_ids, debug_usd = [], 0.0, [], 0.0
        for p in g.patterns:
            if g.name.startswith("/aws/lambda/") and LAMBDA_PLATFORM.search(p.text):
                p.flags.append("lambda_platform")
                lambda_ids.append(p.id)
                lambda_usd += p.monthly_usd
                dropped[p.id] = p.monthly_usd
                continue
            if (p.severity.lower() in ("debug", "trace") or DEBUG.search(p.text)) and is_prod_like(g.name):
                p.flags.append("debug_in_prod")
                debug_ids.append(p.id)
                debug_usd += p.monthly_usd
                dropped[p.id] = p.monthly_usd
            if p.byte_share >= NOISY_SHARE or p.monthly_usd >= NOISY_MIN_USD:
                p.flags.append("noisy")
                if p.monthly_usd >= MIN_USD:
                    out.append(Suggestion(
                        "noisy_pattern", g.region, g.name, "Drop or sample a noisy log line",
                        f"About {p.byte_share:.0%} of this group's bytes ({p.ratio:.0%} of events). "
                        f"Dropping it saves the full amount; logging 1 in 10 saves 90%.",
                        p.monthly_usd, [p.id]))
                    dropped[p.id] = p.monthly_usd
        if lambda_usd >= MIN_USD:
            fn = g.name[len("/aws/lambda/"):]
            out.append(Suggestion(
                "lambda_platform", g.region, g.name, "Lambda START/END/REPORT lines",
                "Platform lines on every invocation. JSON log format with system log level WARN drops them "
                "(Duration and memory stay in AWS/Lambda metrics). JSON format also reshapes your own log lines: "
                "check parsers and metric filters first.", lambda_usd, lambda_ids,
                command=_cmd("aws", "lambda", "update-function-configuration", "--region", g.region,
                             "--function-name", fn, "--logging-config", "LogFormat=JSON,SystemLogLevel=WARN")))
        if debug_usd >= MIN_USD:
            out.append(Suggestion(
                "debug_in_prod", g.region, g.name, "DEBUG-level lines in what looks like prod",
                "Raise the log level to INFO in production (`logbill locate` finds the lines).",
                debug_usd, debug_ids))
        drop_usd = min(sum(dropped.values()), g.ingest_usd)

        if CONTAINER_INSIGHTS.match(g.name) and g.ingest_usd >= MIN_USD:
            out.append(Suggestion(
                "container_insights", g.region, g.name, "Container Insights performance events",
                "Metrics shipped as log events. Turn Container Insights off on clusters nobody watches "
                "(aws ecs update-cluster-settings ... containerInsights=disabled), or keep it with short retention.",
                g.ingest_usd))
            drop_usd = g.ingest_usd

        ia_save = 0.0
        ok, _ = ia_eligible(g)
        if ok and g.ingest_usd >= MIN_USD and not CONTAINER_INSIGHTS.match(g.name):
            full = ia_saving(g, prices)
            if full >= MIN_USD:
                rq = "unknown" if g.recent_queries is None else str(g.recent_queries)
                out.append(Suggestion(
                    "infrequent_access", g.region, g.name, "Move to the Infrequent Access log class",
                    f"No metric or subscription filters; recent Insights queries: {rq}. "
                    "The class is fixed at creation: create a new group in Infrequent Access and point the "
                    "writer at it. You lose Live Tail and filters; Insights still works.", full))
            ia_save = ia_saving(g, prices, g.ingest_usd - drop_usd)
        combined += storage_save + drop_usd + ia_save
    out.sort(key=lambda s: s.monthly_usd, reverse=True)
    return out, combined

