"""One deterministic tick: query sources -> fingerprint -> dedupe -> rules -> redacted documents. No LLM."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import findings as fnd
from . import rules as rl
from . import state as st
from .config import AwsSourceConfig, Config, GcpSourceConfig
from .sources import SourceError, Window

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_NEW = 10


@dataclass
class TickResult:
    findings: dict
    ingest: dict
    state: dict
    exit_code: int


def default_severity(event) -> str:
    return "high" if event.kind in ("alarm", "alb") else "medium"


def build_sources(config: Config):
    from .sources.aws import AwsSource
    from .sources.gcp import GcpSource

    out = []
    for s in config.sources:
        if isinstance(s, AwsSourceConfig):
            out.append(AwsSource(s, config.limits))
        elif isinstance(s, GcpSourceConfig):
            out.append(GcpSource(s, config.limits))
    return out


def _parse_iso(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def source_window(state: dict, source_id: str, end: datetime, minutes: int) -> Window:
    # Start where the last successful tick of this source ended, so overlapping
    # schedules don't count the same events twice; never look back past `minutes`.
    start = end - timedelta(minutes=minutes)
    last = _parse_iso(state["windows"].get(source_id))
    if last and start < last < end:
        start = last
    return Window(start, end)


def run(config: Config, state: dict, window_minutes: int = 60, now: datetime | None = None,
        sources=None, baseline_only: bool = False) -> TickResult:
    now = (now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    sources = build_sources(config) if sources is None else sources
    limits = config.limits

    events, source_rows = [], []
    for src in sources:
        window = source_window(state, src.id, now, window_minutes)
        row = {"id": src.id, "type": src.type, "ok": True, "error_code": None, "truncated": False}
        try:
            got = src.events(window)
            events.extend(got)
            state["windows"][src.id] = fnd.iso(now)
            row["truncated"] = bool(getattr(src, "truncated", False))
        except SourceError as e:
            row.update(ok=False, error_code=e.code)
        source_rows.append(row)

    groups: dict[str, dict] = {}
    for ev in events:
        g = groups.setdefault(ev.fingerprint, {"event": ev, "count": 0, "first": None, "last": None})
        g["count"] += ev.count
        if ev.timestamp:
            g["first"] = min(filter(None, [g["first"], ev.timestamp]))
            g["last"] = max(filter(None, [g["last"], ev.timestamp]))

    summary = {"events": sum(g["count"] for g in groups.values()), "fingerprints": len(groups),
               "new": 0, "spike": 0, "known": 0, "ignored": 0, "truncated": 0}
    out = []
    for fp, g in groups.items():
        ev, count = g["event"], g["count"]
        status, base = st.classify(state, fp, count, limits["spike_factor"], limits["spike_min_count"])
        if baseline_only:
            status = "known"
        facts = {
            "source": ev.source, "source_id": ev.source_id, "kind": ev.kind, "service": ev.service,
            "route": ev.route, "method": ev.method, "status": ev.status, "error": ev.stem,
            "error_class": ev.error_class, "alarm": ev.alarm, "count": count,
            "severity": default_severity(ev), "fingerprint": fp,
        }
        verdict = rl.apply(config.rules, facts)
        entry = st.record(state, fp, count, now, first_seen=g["first"])
        if verdict["ignore"]:
            summary["ignored"] += 1
            continue
        summary[status] += 1
        if status == "known":
            continue
        out.append(fnd.finding(
            ev, status, verdict["severity"], count, base,
            first_seen=_parse_iso(entry["first_seen"]), last_seen=g["last"] or now,
            rules=verdict["rules"], notify=verdict["notify"], phi_mode=config.phi_mode,
        ))

    out.sort(key=fnd.sort_key)
    cap = limits["max_findings"]
    summary["truncated"] = max(0, len(out) - cap)
    out = out[:cap]

    span = Window(now - timedelta(minutes=window_minutes), now)
    doc = fnd.findings_doc(span, config.phi_mode, source_rows, out, summary, now)
    ingest = fnd.ingest_doc(doc)

    if source_rows and not any(r["ok"] for r in source_rows):
        code = EXIT_ERROR
    elif summary["new"]:
        code = EXIT_NEW
    else:
        code = EXIT_OK
    return TickResult(doc, ingest, state, code)
