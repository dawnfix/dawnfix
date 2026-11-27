"""Before/after attribution for one deploy, and the comment that reports it."""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from . import __version__
from .constants import BRAND, CE_USD_PER_REQUEST, HOMEPAGE, MARKER_PREFIX

REGION_PREFIX = re.compile(r"^[A-Z]{2,4}\d?-(?=[A-Za-z])")
# (service regex, usage-type regex on the region-stripped type, label). First match wins.
FRIENDLY = [
    (r".", r"^NatGateway-Bytes$", "NAT Gateway data processing"),
    (r".", r"^NatGateway-Hours$", "NAT Gateway hours"),
    (r".", r"^DataTransfer-Out-Bytes$", "data transfer out to the internet"),
    (r".", r"^DataTransfer-Regional-Bytes$", "cross-AZ data transfer"),
    (r".", r"-AWS-(Out|In)-Bytes$", "inter-region data transfer"),
    (r".", r"^BoxUsage:(?P<x>.+)$", "EC2 {x} instance hours"),
    (r".", r"^SpotUsage:(?P<x>.+)$", "EC2 {x} spot hours"),
    (r".", r"^EBS:VolumeUsage\.?(?P<x>.*)$", "EBS {x} storage"),
    (r".", r"^EBS:SnapshotUsage", "EBS snapshot storage"),
    (r".", r"^PublicIPv4:(InUse|Idle)Address$", "public IPv4 addresses"),
    (r".", r"^LoadBalancerUsage$", "load balancer hours"),
    (r".", r"^LCUUsage$", "load balancer LCUs"),
    (r".", r"^Fargate-vCPU-Hours", "Fargate vCPU"),
    (r".", r"^Fargate-GB-Hours", "Fargate memory"),
    (r".", r"^InstanceUsage:(?P<x>db\..+)$", "RDS {x} instance hours"),
    (r".", r"^Lambda-GB-Second", "Lambda compute"),
    (r"CloudWatch", r"^DataProcessing-Bytes$", "CloudWatch Logs ingestion"),
    (r"CloudWatch", r"^TimedStorage-ByteHrs$", "CloudWatch Logs storage"),
    (r"Simple Storage", r"^TimedStorage-ByteHrs$", "S3 storage"),
    (r"Simple Storage", r"^Requests-Tier1$", "S3 PUT/LIST requests"),
    (r"Simple Storage", r"^Requests-Tier2$", "S3 GET requests"),
]


def friendly(key: str) -> str:
    """'EC2 - Other | USE1-NatGateway-Bytes' -> 'NAT Gateway data processing'."""
    service, _, usage = key.partition(" | ")
    if not usage:
        return service
    stripped = REGION_PREFIX.sub("", usage)
    for svc_re, use_re, label in FRIENDLY:
        m = re.search(use_re, stripped)
        if m and re.search(svc_re, service):
            return label.format(**m.groupdict()).replace("  ", " ").strip()
    return f"{service}: {stripped}"


def parse_window(s: str) -> int:
    m = re.fullmatch(r"(\d+)d?", s.strip())
    if not m or not 1 <= int(m.group(1)) <= 30:
        raise ValueError(f"bad window {s!r}: use 1d..30d")
    return int(m.group(1))


@dataclass
class Plan:
    """Which days to compare, given the deploy time, the window, now and CE's lag."""
    deployed_at: datetime
    window: int
    now: datetime
    lag_hours: int = 24

    @property
    def deploy_day(self) -> date:
        return self.deployed_at.astimezone(timezone.utc).date()

    @property
    def before_days(self) -> list[date]:
        return [self.deploy_day - timedelta(days=i) for i in range(self.window, 0, -1)]

    @property
    def wanted_after(self) -> list[date]:
        return [self.deploy_day + timedelta(days=i) for i in range(1, self.window + 1)]

    def complete(self, day: date) -> bool:
        end = datetime.combine(day + timedelta(days=1), datetime.min.time(), timezone.utc)
        return self.now >= end + timedelta(hours=self.lag_hours)

    @property
    def after_days(self) -> list[date]:
        return [d for d in self.wanted_after if self.complete(d)]

    @property
    def final(self) -> bool:
        return len(self.after_days) == self.window


@dataclass
class Line:
    key: str
    label: str
    before: float
    after: float

    @property
    def delta(self) -> float:
        return self.after - self.before


@dataclass
class Result:
    sha: str
    plan: Plan
    lines: list[Line] = field(default_factory=list)
    tag_key: str | None = None
    metric: str = "UnblendedCost"
    tag_lines: list[Line] = field(default_factory=list)
    before_totals: list[float] = field(default_factory=list)
    estimated_days: list[date] = field(default_factory=list)
    ce_requests: int = 0
    ce_cache_hits: int = 0
    noise_floor_usd: float = 1.0
    noise_pct: float = 3.0

    @property
    def before(self) -> float:
        return sum(l.before for l in self.lines)

    @property
    def after(self) -> float:
        return sum(l.after for l in self.lines)

    @property
    def delta(self) -> float:
        return self.after - self.before

    @property
    def stdev(self) -> float:
        return statistics.pstdev(self.before_totals) if len(self.before_totals) > 1 else 0.0

    @property
    def material(self) -> bool:
        threshold = max(self.noise_floor_usd, self.before * self.noise_pct / 100, 2 * self.stdev)
        return abs(self.delta) >= threshold

    def drivers(self) -> list[Line]:
        """Lines moving the same way as the total, biggest first."""
        sign = 1 if self.delta >= 0 else -1
        return sorted((l for l in self.lines if l.delta * sign > 0), key=lambda l: -abs(l.delta))

    def headline(self) -> str:
        short = self.sha[:7]
        if not self.plan.after_days:
            return f"deploy {short}: waiting for Cost Explorer data (it lags about a day)"
        if not self.material:
            return f"deploy {short}: no material cost change ({_signed(self.delta)}/day, within day-to-day noise)"
        pct = f" ({self.delta / self.before * 100:+.0f}%)" if self.before > 0 else ""
        d = self.drivers()
        if not d:
            return f"deploy {short}: {_signed(self.delta)}/day{pct}"
        top = d[0]
        if abs(top.delta) >= 0.5 * abs(self.delta):
            why = f"mostly {top.label} ({_signed(top.delta)}/day)"
        else:
            why = "led by " + " and ".join(f"{l.label} ({_signed(l.delta)})" for l in d[:2])
        return f"deploy {short}: {_signed(self.delta)}/day{pct}, {why}"

    def to_dict(self) -> dict:
        p = self.plan
        return {
            "version": __version__, "sha": self.sha, "deployed_at": _iso(p.deployed_at), "window_days": p.window,
            "before_days": [d.isoformat() for d in p.before_days],
            "after_days": [d.isoformat() for d in p.after_days],
            "final": p.final, "headline": self.headline(), "material": self.material,
            "before_usd_per_day": round(self.before, 2), "after_usd_per_day": round(self.after, 2),
            "delta_usd_per_day": round(self.delta, 2), "baseline_stdev": round(self.stdev, 2),
            "lines": [_line(l) for l in sorted(self.lines, key=lambda l: -abs(l.delta))],
            "tag_key": self.tag_key, "tag_lines": [_line(l) for l in sorted(self.tag_lines, key=lambda l: -abs(l.delta))],
            "ce_requests": self.ce_requests, "ce_cache_hits": self.ce_cache_hits,
        }


def _line(l: Line) -> dict:
    return {"key": l.key, "label": l.label, "before": round(l.before, 4), "after": round(l.after, 4),
            "delta": round(l.delta, 4)}


def _signed(v: float) -> str:
    return f"{'+' if v >= 0 else '-'}${abs(v):,.2f}"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def averages(series: dict[str, dict[date, float]], before: list[date], after: list[date],
             label=friendly) -> list[Line]:
    out = []
    for key, by_day in series.items():
        b = sum(by_day.get(d, 0.0) for d in before) / len(before) if before else 0.0
        a = sum(by_day.get(d, 0.0) for d in after) / len(after) if after else 0.0
        if b or a:
            out.append(Line(key, label(key), b, a))
    return out


def marker(sha: str) -> str:
    return f"<!-- {MARKER_PREFIX}:sha={sha} -->"


def comment(r: Result, top: int = 8) -> str:
    p = r.plan
    fmt = "%b %d"
    rng = lambda ds: f"{ds[0].strftime(fmt)}–{ds[-1].strftime(fmt)}" if ds else "none yet"  # noqa: E731
    out = [marker(r.sha), f"### {r.headline()}", ""]
    out.append(f"Deployed {_iso(p.deployed_at)}. {p.window} day(s) before ({rng(p.before_days)}) vs "
               f"{len(p.after_days)} of {p.window} day(s) after ({rng(p.after_days)}); the deploy day is left out. "
               f"Daily {r.metric}, credits and refunds excluded.")
    out.append("")
    if p.after_days:
        out += [f"Total: **${r.before:,.2f}/day → ${r.after:,.2f}/day** ({_signed(r.delta)}/day; "
                f"baseline day-to-day spread ±${r.stdev:,.2f})", ""]
        rows = sorted(r.lines, key=lambda l: -abs(l.delta))[:top]
        out += ["| What changed | Before $/day | After $/day | Δ $/day |", "|---|---:|---:|---:|"]
        out += [f"| {l.label} | {l.before:,.2f} | {l.after:,.2f} | {_signed(l.delta)} |" for l in rows]
        if len(r.lines) > top:
            rest = sum(l.delta for l in sorted(r.lines, key=lambda l: -abs(l.delta))[top:])
            out.append(f"| {len(r.lines) - top} other line(s) | | | {_signed(rest)} |")
        out.append("")
        if r.tag_key and r.tag_lines:
            out += [f"By tag `{r.tag_key}`:", "", "| Tag value | Before $/day | After $/day | Δ $/day |",
                    "|---|---:|---:|---:|"]
            out += [f"| {l.label} | {l.before:,.2f} | {l.after:,.2f} | {_signed(l.delta)} |"
                    for l in sorted(r.tag_lines, key=lambda l: -abs(l.delta))[:top]]
            out.append("")
    if not p.final:
        out += [f"_Provisional: Cost Explorer lags about {p.lag_hours}h. Re-run after "
                f"{_iso(datetime.combine(p.wanted_after[-1] + timedelta(days=1), datetime.min.time(), timezone.utc) + timedelta(hours=p.lag_hours))} "
                "for the final numbers; this comment updates in place._", ""]
    out.append(f"<sub>Correlation, not causation: traffic and other deploys in the window move cost too. "
               f"Cost Explorer requests this run: {r.ce_requests} (≈${r.ce_requests * CE_USD_PER_REQUEST:.2f}), "
               f"cache hits: {r.ce_cache_hits}. {BRAND} {__version__} · {HOMEPAGE}</sub>")
    return "\n".join(out) + "\n"
