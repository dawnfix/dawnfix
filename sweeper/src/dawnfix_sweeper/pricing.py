"""Price table: list prices per region from the AWS Price List bulk API, recorded in prices.json.

The tool never fetches prices live. ``tools/refresh_prices.py`` rebuilds prices.json from
the public, unauthenticated offer files; every entry names its offer and usage type, and
the few entries that are not in an offer file carry ``"estimated": true`` and a source URL.
A region missing from the table is priced at ``default_region`` (us-east-1) and the plan
says so.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).with_name("prices.json")
# Engines priced per instance class; others are left unpriced (the plan says so).
RDS_ENGINES = {"mysql": "mysql", "postgres": "postgres", "mariadb": "mysql"}


@dataclass
class Prices:
    doc: dict

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Prices":
        return cls(json.loads(Path(path or DEFAULT_PATH).read_text()))

    @property
    def hours(self) -> int:
        return int(self.doc.get("hours_per_month", 730))

    @property
    def default_region(self) -> str:
        return self.doc.get("default_region", "us-east-1")

    @property
    def regions(self) -> list[str]:
        return list(self.doc.get("regions", [self.default_region]))

    def has_region(self, region: str) -> bool:
        return region in self.regions

    def region(self, region: str) -> "RegionPrices":
        return RegionPrices(self, region)

    def get(self, key: str, region: str | None = None) -> float | None:
        entry = self.doc["prices"].get(key)
        if entry is None:
            return None
        if "usd" in entry:  # one price for every region (a hand-written --prices file)
            return float(entry["usd"])
        by_region = entry.get("regions", {})
        v = by_region.get(region or self.default_region, by_region.get(self.default_region))
        return None if v is None else float(v)

    def meta(self) -> dict:
        src = self.doc.get("source", {})
        sources = {e["source"] for e in self.doc["prices"].values() if e.get("source")}
        sources |= {o["url"] for o in src.get("offers", {}).values() if o.get("url")}
        return {
            "as_of": self.doc.get("as_of"),
            "regions": self.regions,
            "default_region": self.default_region,
            "note": self.doc.get("note"),
            "publication_dates": {k: o.get("publication_date") for k, o in src.get("offers", {}).items()},
            "estimated": sorted(k for k, e in self.doc["prices"].items() if e.get("estimated")),
            "sources": sorted(sources),
        }


@dataclass
class RegionPrices:
    """One region's view of the table; every per-resource estimate lives here."""
    table: Prices
    name: str

    def get(self, key: str) -> float | None:
        return self.table.get(key, self.name)

    def monthly_hourly(self, key: str) -> float | None:
        p = self.get(key)
        return None if p is None else p * self.table.hours

    def ebs_volume(self, vtype: str, size_gb: int, iops: int | None, throughput: int | None) -> float | None:
        gb = self.get(f"ebs_gb_month.{vtype}")
        if gb is None:
            return None
        total = gb * size_gb
        if vtype in ("io1", "io2") and iops:
            total += (self.get(f"ebs_iops_month.{vtype}") or 0) * iops
        if vtype == "gp3":
            total += (self.get("ebs_iops_month.gp3") or 0) * max(0, (iops or 3000) - 3000)
            total += (self.get("ebs_throughput_month.gp3") or 0) * max(0, (throughput or 125) - 125)
        return total

    def snapshot(self, size_gb: float) -> float | None:
        p = self.get("snapshot_gb_month")
        return None if p is None else p * size_gb

    def public_ipv4(self) -> float | None:
        return self.monthly_hourly("public_ipv4_hour")

    def load_balancer(self, lb_type: str) -> float | None:
        key = {"application": "alb_hour", "network": "nlb_hour", "gateway": "gwlb_hour",
               "classic": "clb_hour"}.get(lb_type)
        return self.monthly_hourly(key) if key else None

    def log_storage(self, stored_bytes: int) -> float | None:
        p = self.get("log_storage_gb_month")
        return None if p is None else p * stored_bytes / 1e9

    def ec2(self, instance_type: str) -> float | None:
        return self.monthly_hourly(f"ec2_hour.{instance_type}")

    def nat_gateway(self) -> float | None:
        return self.monthly_hourly("nat_gateway_hour")

    def nat_gb(self) -> float | None:
        return self.get("nat_gateway_gb")

    def rds_instance(self, db_class: str, engine: str, multi_az: bool) -> float | None:
        family = next((v for k, v in RDS_ENGINES.items() if engine.startswith(k)), None)
        if family is None:
            return None
        p = self.monthly_hourly(f"rds_hour.{family}.{db_class}")
        return None if p is None else p * (2 if multi_az else 1)

    def rds_storage(self, storage_type: str, size_gb: int, multi_az: bool) -> float | None:
        p = self.get(f"rds_storage_gb_month.{storage_type}")
        return None if p is None else p * size_gb * (2 if multi_az else 1)

    def rds_snapshot(self, size_gb: float) -> float | None:
        p = self.get("rds_backup_gb_month")
        return None if p is None else p * size_gb
