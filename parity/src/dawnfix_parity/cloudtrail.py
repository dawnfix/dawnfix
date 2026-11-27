"""Opt-in: who reads which secret/parameter, from CloudTrail event history (LookupEvents).

LookupEvents is limited to 2 requests/second per account per region and only covers the
last 90 days of management events, so this is rate-limited and capped. CloudTrail never
records secret values, only names and principals.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .aws import AwsError, ReadOnlyViolation, error_code

READ_EVENTS = {
    "secretsmanager": ["GetSecretValue"],
    "ssm": ["GetParameter", "GetParameters", "GetParametersByPath"],
}
MAX_DAYS = 90


class RateLimiter:
    def __init__(self, per_second: float = 1.5, clock=time.monotonic, sleep=time.sleep):
        self.interval = 1.0 / per_second
        self.clock, self.sleep = clock, sleep
        self._last: float | None = None
        self.waits = 0

    def wait(self):
        now = self.clock()
        if self._last is not None:
            delay = self.interval - (now - self._last)
            if delay > 0:
                self.waits += 1
                self.sleep(delay)
                now = self.clock()
        self._last = now


@dataclass
class Reads:
    """target name -> principal -> count, plus last-read time per target."""

    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    last: dict[str, datetime] = field(default_factory=dict)
    prefix_reads: dict[str, dict[str, int]] = field(default_factory=dict)  # GetParametersByPath
    days: int = 0
    truncated: bool = False
    calls: int = 0

    def add(self, target: str, principal: str, when: datetime | None, prefix=False):
        bucket = self.prefix_reads if prefix else self.counts
        per = bucket.setdefault(target, {})
        per[principal] = per.get(principal, 0) + 1
        if when and (target not in self.last or when > self.last[target]):
            self.last[target] = when

    def readers_of(self, name: str, arn: str | None = None) -> dict[str, int]:
        out: dict[str, int] = {}
        for t in {name, arn} - {None}:
            for p, n in self.counts.get(t, {}).items():
                out[p] = out.get(p, 0) + n
        for prefix, per in self.prefix_reads.items():
            if name.startswith(prefix.rstrip("/") + "/"):
                for p, n in per.items():
                    out[p] = out.get(p, 0) + n
        return out

    def last_read(self, name: str, arn: str | None = None):
        cands = [self.last[t] for t in (name, arn) if t and t in self.last]
        for prefix in self.prefix_reads:
            if name.startswith(prefix.rstrip("/") + "/") and prefix in self.last:
                cands.append(self.last[prefix])
        return max(cands) if cands else None


def _principal(ev: dict) -> str:
    ui = ev.get("userIdentity") or {}
    issuer = ((ui.get("sessionContext") or {}).get("sessionIssuer") or {}).get("arn")
    return issuer or ui.get("arn") or ui.get("invokedBy") or ui.get("type") or "unknown"


def _targets(name: str, params: dict) -> list[tuple[str, bool]]:
    if not isinstance(params, dict):
        return []
    if name == "GetSecretValue":
        return [(params["secretId"], False)] if params.get("secretId") else []
    if name == "GetParameter":
        return [(params["name"], False)] if params.get("name") else []
    if name == "GetParameters":
        return [(n, False) for n in params.get("names") or []]
    if name == "GetParametersByPath":
        return [(params["path"], True)] if params.get("path") else []
    return []


def lookup_reads(client, now: datetime, days: int = 30, max_pages: int = 20,
                 limiter: RateLimiter | None = None, services=("secretsmanager", "ssm")) -> Reads:
    days = max(1, min(int(days), MAX_DAYS))
    limiter = limiter or RateLimiter()
    reads = Reads(days=days)
    start = now - timedelta(days=days)
    for svc in services:
        for event_name in READ_EVENTS[svc]:
            params = {"LookupAttributes": [{"AttributeKey": "EventName", "AttributeValue": event_name}],
                      "StartTime": start, "EndTime": now, "MaxResults": 50}
            for page in range(max_pages):
                limiter.wait()
                try:
                    resp = client.lookup_events(**params)
                except ReadOnlyViolation:
                    raise
                except Exception as e:
                    raise AwsError(error_code(e), "cloudtrail:LookupEvents") from None
                reads.calls += 1
                for e in resp.get("Events", []):
                    try:
                        ev = json.loads(e.get("CloudTrailEvent") or "{}")
                    except ValueError:
                        continue
                    if ev.get("errorCode"):
                        continue   # denied/failed reads are not reads
                    when = e.get("EventTime")
                    for target, is_prefix in _targets(event_name, ev.get("requestParameters") or {}):
                        reads.add(target, _principal(ev), when, prefix=is_prefix)
                token = resp.get("NextToken")
                if not token:
                    break
                params["NextToken"] = token
            else:
                reads.truncated = True
    return reads
