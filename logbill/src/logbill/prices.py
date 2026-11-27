"""Price table (prices.json) and the arithmetic on it."""
import json
import os
from pathlib import Path

GB = 1024 ** 3  # AWS bills CloudWatch Logs per GB = 2^30 bytes
DAYS_PER_MONTH = 30


def default_path() -> Path:
    env = os.environ.get("LOGBILL_PRICES")
    return Path(env) if env else Path(__file__).with_name("prices.json")


class Prices:
    def __init__(self, doc: dict):
        self.doc = doc
        self.regions = doc["regions"]
        self.default_region = doc.get("default_region", "us-east-1")
        self.vended_prefixes = tuple(doc.get("vended_prefixes", ()))
        self.free_tier_gb = float(doc.get("free_tier", {}).get("gb_per_month", 0))

    @classmethod
    def load(cls, path: str | os.PathLike | None = None) -> "Prices":
        return cls(json.loads(Path(path or default_path()).read_text()))

    def region(self, region: str) -> tuple[dict, bool]:
        """(rates, approximate). Unknown regions use the default region's rates."""
        if region in self.regions:
            return self.regions[region], False
        return self.regions[self.default_region], True

    def ingest_rate(self, region: str, log_class: str) -> float:
        r, _ = self.region(region)
        return r["ingest_ia_gb"] if log_class == "INFREQUENT_ACCESS" else r["ingest_standard_gb"]

    def storage_rate(self, region: str) -> float:
        return self.region(region)[0]["storage_gb_month"]

    def insights_rate(self, region: str) -> float:
        return self.region(region)[0]["insights_scanned_gb"]

    def vended_tiers(self, region: str, log_class: str) -> list:
        r, _ = self.region(region)
        return r["vended_ia_tiers"] if log_class == "INFREQUENT_ACCESS" else r["vended_standard_tiers"]

    def is_vended(self, name: str) -> bool:
        return name.startswith(self.vended_prefixes)

    def source(self) -> dict:
        return self.doc.get("source", {})


def tiered_cost(tiers: list, gb: float) -> float:
    """Cost of `gb` on [[up_to_gb | None, usd_per_gb], ...] tiers (cumulative bounds)."""
    cost, lower = 0.0, 0.0
    for upper, rate in tiers:
        if gb <= lower:
            break
        top = gb if upper is None else min(gb, float(upper))
        cost += (top - lower) * rate
        if upper is None:
            break
        lower = float(upper)
    return cost


def usd(x: float) -> str:
    if abs(x) >= 100:
        return f"${x:,.0f}"
    return f"${x:,.2f}"


def gb_str(b: float) -> str:
    g = b / GB
    if g >= 100:
        return f"{g:,.0f} GB"
    if g >= 1:
        return f"{g:,.1f} GB"
    return f"{b / 1024 ** 2:,.1f} MB"
