"""Builds findings.json (for the fix job) and the ingest payload (the only thing sent to the hosted service)."""
import re

from .redact import safe_redact

FINDINGS_SCHEMA = "dawnfix.findings/1"
INGEST_SCHEMA = "dawnfix.ingest/1"
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
STATUS_ORDER = {"new": 0, "spike": 1}

# Length caps for every free-ish string in findings.json (mirrored in the JSON Schema).
CAPS = {"service": 128, "route": 200, "error": 160, "sample": 300, "rule": 64, "source_id": 80}
# Values that are generated here, not taken from logs: skip redaction (timestamps would survive it anyway).
# error_code is already reduced to [A-Za-z0-9_.-] by SourceError.
SAFE_KEYS = {"schema", "generated_at", "start", "end", "first_seen", "last_seen", "fingerprint", "error_code"}
ROUTE_OK = re.compile(r"^(/[A-Za-z0-9_.:-]*)*$")
CLASS_OK = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


def iso(dt) -> str | None:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def _cap(key, value):
    cap = CAPS.get(key)
    return value[:cap] if cap and isinstance(value, str) else value


def scrub(obj, key=None):
    """Redacts every string in a document, then applies the length caps."""
    if isinstance(obj, dict):
        return {k: scrub(v, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v, "rule" if key == "rules" else key) for v in obj]
    if isinstance(obj, str) and key not in SAFE_KEYS:
        return _cap(key, safe_redact(obj))
    return obj


def sort_key(f: dict):
    return (STATUS_ORDER.get(f["status"], 9), SEVERITY_ORDER[f["severity"]], -f["count"], f["fingerprint"])


def finding(event, status, severity, count, baseline, first_seen, last_seen, rules, notify, phi_mode) -> dict:
    f = {
        "fingerprint": event.fingerprint,
        "status": status,
        "severity": severity,
        "source": event.source,
        "source_id": event.source_id,
        "kind": event.kind,
        "service": event.service,
        "route": event.route,
        "method": event.method,
        "http_status": event.status,
        "error_class": event.error_class if CLASS_OK.match(event.error_class or "") else "Error",
        "count": count,
        "baseline": baseline,
        "first_seen": iso(first_seen),
        "last_seen": iso(last_seen),
        "rules": rules[:20],
        "notify": notify,
    }
    if not phi_mode:
        # Only outside PHI mode does any text derived from a log message leave.
        f["error"] = event.stem
        if event.message:
            f["sample"] = event.message
    return f


def findings_doc(window, phi_mode, sources, findings, summary, generated_at) -> dict:
    doc = scrub({
        "schema": FINDINGS_SCHEMA,
        "generated_at": iso(generated_at),
        "window": {"start": iso(window.start), "end": iso(window.end), "minutes": window.minutes},
        "phi_mode": phi_mode,
        "sources": sources,
        "summary": summary,
        "findings": findings,
    })
    for f in doc["findings"]:
        # Redaction can turn a template into something the schema refuses; fold it.
        if not ROUTE_OK.match(f["route"]):
            f["route"] = "/:unmatched"
        if not CLASS_OK.match(f["error_class"]):
            f["error_class"] = "Error"
    return doc


def ingest_doc(doc: dict) -> dict:
    """Projection of findings.json onto the strict allowlist: enums, counts, hashes, route templates."""
    out = []
    for f in doc["findings"]:
        route = f["route"]
        out.append({
            "fingerprint": f["fingerprint"],
            "status": f["status"],
            "severity": f["severity"],
            "source": f["source"],
            "kind": f["kind"],
            "route": route if f["kind"] == "log" else "",
            "method": f["method"],
            "http_status": f["http_status"],
            "error_class": f["error_class"],
            "count": f["count"],
            "pr_url": None,
        })
    s = doc["summary"]
    return {
        "schema": INGEST_SCHEMA,
        "generated_at": doc["generated_at"],
        "window_minutes": doc["window"]["minutes"],
        "phi_mode": doc["phi_mode"],
        "counts": {k: s[k] for k in ("events", "new", "spike", "known", "ignored")},
        "sources": [{"type": x["type"], "ok": x["ok"], "error_code": x["error_code"]} for x in doc["sources"]],
        "findings": out,
    }
