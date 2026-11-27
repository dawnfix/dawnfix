"""Cost Explorer reads with a disk cache. CE bills $0.01 per request, so every request is counted.

A cached response is reused forever once every day in it has settled (CE revises recent
days for a while), and for `ttl_hours` otherwise, so re-running the same receipt is free.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

MAX_PAGES = 50
# Credits and refunds land on arbitrary days and would swamp a per-deploy delta.
EXCLUDE_CREDITS = {"Not": {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", "Refund"]}}}


@dataclass
class Cache:
    root: Path | None
    settle_hours: int = 72
    ttl_hours: int = 6
    requests: int = 0  # CE requests actually sent
    hits: int = 0
    _log: list = field(default_factory=list)

    def _path(self, key: str) -> Path:
        return self.root / f"ce-{key}.json"

    def get(self, key: str, end: date, now: datetime):
        if self.root is None or not self._path(key).exists():
            return None
        doc = json.loads(self._path(key).read_text())
        fetched = datetime.fromisoformat(doc["fetched_at"])
        settled = fetched >= datetime.combine(end, datetime.min.time(), timezone.utc) + timedelta(hours=self.settle_hours)
        if settled or now - fetched < timedelta(hours=self.ttl_hours):
            self.hits += 1
            return doc["pages"]
        return None

    def put(self, key: str, pages: list, now: datetime) -> None:
        if self.root is None:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        self._path(key).write_text(json.dumps({"fetched_at": now.isoformat(), "pages": pages}, default=str))


def request_for(start: date, end: date, group_by: list[dict], metric: str) -> dict:
    return {
        "TimePeriod": {"Start": start.isoformat(), "End": end.isoformat()},  # End is exclusive
        "Granularity": "DAILY",
        "Metrics": [metric],
        "GroupBy": group_by,
        "Filter": EXCLUDE_CREDITS,
    }


def fetch(ce, req: dict, cache: Cache, now: datetime) -> list[dict]:
    """All ResultsByTime pages for one request, from cache when allowed."""
    key = hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()[:24]
    end = date.fromisoformat(req["TimePeriod"]["End"])
    hit = cache.get(key, end, now)
    if hit is not None:
        return hit
    params, results = dict(req), []
    for _ in range(MAX_PAGES):
        resp = ce.get_cost_and_usage(**params)
        cache.requests += 1
        results.extend(resp.get("ResultsByTime", []))
        token = resp.get("NextPageToken")
        if not token:
            break
        params["NextPageToken"] = token
    cache.put(key, results, now)
    return results


def daily_by_key(results: list[dict], metric: str) -> tuple[dict[str, dict[date, float]], set[date]]:
    """{group label: {day: usd}} and the set of days CE marked Estimated."""
    out: dict[str, dict[date, float]] = {}
    estimated = set()
    for r in results:
        day = date.fromisoformat(r["TimePeriod"]["Start"])
        if r.get("Estimated"):
            estimated.add(day)
        for g in r.get("Groups", []):
            key = " | ".join(g["Keys"])
            amt = float(g["Metrics"][metric]["Amount"])
            out.setdefault(key, {})[day] = out.get(key, {}).get(day, 0.0) + amt
    return out, estimated
