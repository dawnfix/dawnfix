"""Turns raw log lines into templates: route, error class, message stem, fingerprint."""
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import unquote, urlsplit

from .redact import safe_redact

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD")
ID_SEGMENT = re.compile(r"[0-9a-fA-F-]{8,}|\d+|[A-Za-z0-9_-]{20,}")
SAFE_SEGMENT = re.compile(r"[A-Za-z0-9_.:-]*")
MAX_SEGMENTS = 12
ROUTE_MAX = 200
STEM_MAX = 120
CLASS_MAX = 64

ACCESS_LINE = re.compile(r"\b(" + "|".join(METHODS) + r") (/\S*|https?://\S+) (\d{3})\b")
ERROR_CLASS = re.compile(r"\b([A-Z][A-Za-z0-9]*(?:Error|Exception|Fault))\b")
ERRNO = re.compile(r"\b(E(?!RROR\b)[A-Z]{3,15})\b")
TEXT_LEVEL = re.compile(r"\b(ERROR|FATAL|CRITICAL|PANIC)\b|\[error\]|Traceback \(most recent", re.I)
TIMESTAMPS = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ][\d:.,]+(?:Z|[+-]\d{2}:?\d{2})?|\d{2}\.\d{2}\.\d{4} [\d:.]+|\d{2}/\d{2}/\d{2,4} [\d:.]+"
)
LEVEL_TAG = re.compile(r"^\W*(?:\[?(?:ERROR|FATAL|CRITICAL|WARN|INFO|DEBUG)\]?:?\s*)+", re.I)
ERROR_LEVELS = {"error", "fatal", "critical", "alert", "emergency", "panic"}


@dataclass
class Event:
    """One normalized observation from a source. `message` is raw; redact before output."""

    source: str  # aws | gcp
    source_id: str  # e.g. aws:us-east-1, gcp:my-proj
    kind: str  # log | alarm | alb
    service: str
    route: str = ""
    method: str | None = None
    status: int | None = None
    error_class: str = "Error"
    message: str = ""
    timestamp: datetime | None = None
    count: int = 1
    alarm: str = ""
    stem: str = field(default="")

    def __post_init__(self):
        if not self.stem:
            self.stem = error_stem(self.message, self.status, self.error_class)

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.source, self.service, self.route, self.stem)


def _decode(s: str) -> str:
    for _ in range(10):
        d = unquote(s)
        if d == s:
            break
        s = d
    return s


def route_template(url: str) -> str:
    """'/users/123/mail/a%40b.com?x=1' -> '/users/:id/mail/:email'."""
    if not url:
        return ""
    if "://" in url:
        url = urlsplit(url).path or "/"
    u = _decode(url.split("?")[0].split("#")[0])
    u = re.sub(r"[^/]+@[^/]+", ":email", u)
    segs = []
    for x in u.split("/"):
        if ID_SEGMENT.fullmatch(x):
            x = ":id"
        elif not SAFE_SEGMENT.fullmatch(x):
            x = ":x"
        segs.append(x)
    if len(segs) > MAX_SEGMENTS + 1:
        segs = segs[: MAX_SEGMENTS + 1] + ["..."]
    out = "/".join(segs)
    if not out.startswith("/"):
        out = "/" + out
    return out[:ROUTE_MAX]


def clean_class(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "", str(name))[:CLASS_MAX]
    return name if name and name[0].isalpha() else "Error"


def find_error_class(text: str, status: int | None = None) -> str:
    for rx in (ERROR_CLASS, ERRNO):
        m = rx.search(text or "")
        if m:
            return clean_class(m.group(1))
    if status and status >= 500:
        return f"HTTP{status}"
    return "Error"


def error_stem(message: str, status: int | None = None, error_class: str = "Error") -> str:
    """Stable, redacted first-line template of an error message."""
    first = (message or "").strip().splitlines()[0] if (message or "").strip() else ""
    s = TIMESTAMPS.sub("", first)
    s = LEVEL_TAG.sub("", s)
    s = safe_redact(s)
    s = re.sub(r"\b0x[0-9a-fA-F]+\b", ":hex", s)
    s = re.sub(r"(?<![:\w])\d+(?:\.\d+)?", ":n", s)
    s = re.sub(r"\s+", " ", s).strip()[:STEM_MAX]
    if not s:
        s = f"HTTP {status}" if status else error_class
    return s


def fingerprint(source: str, service: str, route: str, stem: str) -> str:
    key = "\x1f".join((source, service, route, stem))
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _get(d, *path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_json_record(d: dict) -> dict:
    """Pulls route/status/error out of common structured log shapes (pino, bunyan, winston, audit)."""
    method = _get(d, "req", "method") or d.get("method") or _get(d, "httpRequest", "requestMethod")
    url = (
        _get(d, "req", "url")
        or d.get("route")
        or d.get("path")
        or d.get("url")
        or _get(d, "httpRequest", "requestUrl")
    )
    status = _int(
        _get(d, "res", "statusCode")
        or d.get("status")
        or d.get("statusCode")
        or _get(d, "httpRequest", "status")
    )
    err = d.get("err") if isinstance(d.get("err"), dict) else d.get("error")
    err_class = None
    err_msg = None
    if isinstance(err, dict):
        err_class = err.get("type") or err.get("name") or err.get("code")
        err_msg = err.get("message")
    elif isinstance(err, str):
        err_msg = err
    message = err_msg or d.get("msg") or d.get("message") or ""
    if not isinstance(message, str):
        message = json.dumps(message)[:500]
    level = d.get("level") if d.get("level") is not None else d.get("severity")
    lvl_num = _int(level)
    is_error = (
        (status is not None and status >= 500)
        or (lvl_num is not None and lvl_num >= 50)
        or (isinstance(level, str) and level.lower() in ERROR_LEVELS)
        or err_class is not None
    )
    error_class = clean_class(err_class) if err_class else find_error_class(message, status)
    return {
        "method": method.upper() if isinstance(method, str) and method.upper() in METHODS else None,
        "route": route_template(url) if isinstance(url, str) else "",
        "status": status,
        "error_class": error_class,
        "message": message,
        "is_error": bool(is_error),
    }


def parse_log_message(text: str) -> dict:
    """Parses one log line (JSON or plain text)."""
    text = text or ""
    s = text.strip()
    if s.startswith("{"):
        try:
            d = json.loads(s)
            if isinstance(d, dict):
                return parse_json_record(d)
        except ValueError:
            pass
    method, route, status = None, "", None
    m = ACCESS_LINE.search(s)
    if m:
        method, route, status = m.group(1), route_template(m.group(2)), int(m.group(3))
        message = s[m.end():].strip() if status >= 500 else s
        # An access line carries no error message: keep only what follows the status
        # when it looks like one, so latency/size numbers don't split fingerprints.
        if not (ERROR_CLASS.search(message) or ERRNO.search(message)):
            message = ""
    else:
        message = s
    error_class = find_error_class(s, status)
    is_error = (status is not None and status >= 500) or bool(TEXT_LEVEL.search(s)) or bool(ERROR_CLASS.search(s))
    return {
        "method": method,
        "route": route,
        "status": status,
        "error_class": error_class,
        "message": message,
        "is_error": is_error,
    }


def service_name(name: str) -> str:
    """Log group / resource name as a stable service label."""
    s = safe_redact(name or "unknown")
    s = re.sub(r"[^A-Za-z0-9_./:-]+", "_", s).strip("/_")
    return s[:128] or "unknown"
