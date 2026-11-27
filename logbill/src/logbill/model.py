"""Log groups and what they cost per month."""
from dataclasses import asdict, dataclass, field

from .prices import DAYS_PER_MONTH, GB, Prices, tiered_cost


@dataclass
class Pattern:
    id: str
    text: str            # redacted
    count: int
    ratio: float          # share of events in the query window
    severity: str = ""
    byte_share: float = 0.0   # estimated share of the group's ingested bytes
    monthly_usd: float = 0.0
    flags: list = field(default_factory=list)


@dataclass
class Group:
    name: str
    region: str
    log_class: str = "STANDARD"
    retention_days: int | None = None
    stored_bytes: int = 0
    created_ms: int | None = None
    metric_filters: int = 0
    subscription_filters: int | None = None   # only fetched for the top groups
    recent_queries: int | None = None          # only fetched for the top groups
    ingested_bytes: float = 0.0                # over the scan window
    ingested_events: float = 0.0
    last_day_bytes: float = 0.0
    days: int = 30
    vended: bool = False
    approx_price: bool = False
    monthly_ingest_gb: float = 0.0
    ingest_usd: float = 0.0
    storage_usd: float = 0.0
    monthly_usd: float = 0.0
    patterns: list = field(default_factory=list)
    insights: dict | None = None

    @property
    def key(self) -> str:
        return f"{self.region}:{self.name}"

    @property
    def never_expires(self) -> bool:
        return self.retention_days is None and self.log_class != "DELIVERY"

    def bytes_per_hour(self) -> float:
        """Conservative (higher of window mean and newest day) for the Insights budget."""
        mean_day = self.ingested_bytes / self.days if self.days else 0.0
        return max(mean_day, self.last_day_bytes) / 24.0

    def age_days(self, now_ms: int) -> float | None:
        if not self.created_ms:
            return None
        return max((now_ms - self.created_ms) / 86_400_000, 1.0)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["never_expires"] = self.never_expires
        return d


def from_api(lg: dict, region: str, prices: Prices) -> Group:
    name = lg["logGroupName"]
    return Group(
        name=name,
        region=region,
        log_class=lg.get("logGroupClass") or "STANDARD",
        retention_days=lg.get("retentionInDays"),
        stored_bytes=int(lg.get("storedBytes") or 0),
        created_ms=lg.get("creationTime"),
        metric_filters=int(lg.get("metricFilterCount") or 0),
        vended=prices.is_vended(name),
    )


def price_groups(groups: list[Group], prices: Prices) -> None:
    """Fill monthly cost fields. Vended groups share their region's tiered price:
    the tier is chosen on the region's vended total, then split by volume."""
    vended_total: dict[tuple, float] = {}
    for g in groups:
        g.approx_price = prices.region(g.region)[1]
        g.monthly_ingest_gb = (g.ingested_bytes / GB) * DAYS_PER_MONTH / g.days if g.days else 0.0
        g.storage_usd = (g.stored_bytes / GB) * prices.storage_rate(g.region)
        if g.log_class == "DELIVERY":
            g.ingest_usd = 0.0
            g.storage_usd = 0.0
        elif g.vended:
            k = (g.region, g.log_class)
            vended_total[k] = vended_total.get(k, 0.0) + g.monthly_ingest_gb
        else:
            g.ingest_usd = g.monthly_ingest_gb * prices.ingest_rate(g.region, g.log_class)
    for (region, cls), total in vended_total.items():
        cost = tiered_cost(prices.vended_tiers(region, cls), total)
        for g in groups:
            if g.vended and g.region == region and g.log_class == cls and total > 0:
                g.ingest_usd = cost * g.monthly_ingest_gb / total
    for g in groups:
        g.monthly_usd = g.ingest_usd + g.storage_usd


def effective_ingest_rate(g: Group) -> float:
    """$/GB actually paid by this group (after vended tiering)."""
    return g.ingest_usd / g.monthly_ingest_gb if g.monthly_ingest_gb else 0.0
