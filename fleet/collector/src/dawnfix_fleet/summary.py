"""The fleet summary document and its validator.

Hand-written to match `fleet/schema/fleet-summary.schema.json` (tests check the two agree,
and the board's TypeScript port in `worker/src/fleet/validate.ts` agrees with the same file).
The collector validates what it is about to write, so a bug here fails locally, not as a 400.
"""
from __future__ import annotations

import re

from . import SCHEMA

PROVIDERS = ("aws", "gcp")
ENVS = ("prod", "staging", "dev", "shared", "other")
CREDENTIALS = ("ok", "denied", "expired", "throttled", "account_mismatch", "error")
STATUSES = ("ok", "denied", "throttled", "error", "skipped", "not_implemented")
CURRENCIES = (None, "USD", "EUR", "GBP", "CHF", "CAD", "AUD", "JPY", "OTHER")

TOP_KEYS = ("schema", "generated_at", "accounts")
ACCOUNT_KEYS = ("account", "provider", "env", "credential", "alarms", "spend", "certs", "orphans")
ALARM_KEYS = ("status", "firing", "stuck_24h")
SPEND_KEYS = ("status", "cached", "currency", "as_of", "this_week_cents", "last_week_cents")
CERT_KEYS = ("status", "total", "in_use", "expired", "expiring_14d", "expiring_30d", "manual_renewal_30d",
             "min_days_left", "truncated")
ORPHAN_KEYS = ("status", "count")

MAX_ACCOUNTS = 50
MAX_COUNT = 1_000_000
MAX_CENTS = 10_000_000_000_000
MAX_DAYS = 36500
GENERATED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REF = re.compile(r"^[0-9a-f]{16}$")


class SummaryError(ValueError):
    def __init__(self, path: str, reason: str):
        super().__init__(f"{path or '/'}: {reason}")
        self.path = path
        self.reason = reason


def empty_alarms(status: str) -> dict:
    return {"status": status, "firing": None, "stuck_24h": None}


def empty_spend(status: str) -> dict:
    return {"status": status, "cached": False, "currency": None, "as_of": None,
            "this_week_cents": None, "last_week_cents": None}


def empty_certs(status: str) -> dict:
    return {"status": status, "total": None, "in_use": None, "expired": None, "expiring_14d": None,
            "expiring_30d": None, "manual_renewal_30d": None, "min_days_left": None, "truncated": False}


def orphans_placeholder() -> dict:
    return {"status": "not_implemented", "count": None}


# --- validation --------------------------------------------------------------------------

def _obj(v, path, keys):
    if type(v) is not dict:
        raise SummaryError(path, "expected an object")
    for k in v:
        if k not in keys:
            raise SummaryError(path, "unknown field")
    for k in keys:
        if k not in v:
            raise SummaryError(f"{path}/{k}", "missing")
    return v


def _one_of(v, path, allowed):
    if v not in allowed or type(v) is bool:
        raise SummaryError(path, "not an allowed value")
    return v


def _int(v, path, lo, hi, nullable=True):
    if v is None and nullable:
        return v
    if type(v) is not int:
        raise SummaryError(path, "expected an integer")
    if not lo <= v <= hi:
        raise SummaryError(path, "out of range")
    return v


def _bool(v, path):
    if type(v) is not bool:
        raise SummaryError(path, "expected a boolean")
    return v


def _str(v, path, pattern, nullable=True):
    if v is None and nullable:
        return v
    if type(v) is not str or not pattern.match(v):
        raise SummaryError(path, "not an allowed value")
    return v


def _numbers_follow_status(check: dict, path: str, numbers: tuple[str, ...], optional: tuple[str, ...] = ()):
    """ok: every number present (except `optional`). Anything else: every number null."""
    ok = check["status"] == "ok"
    for k in numbers:
        if not ok and check[k] is not None:
            raise SummaryError(f"{path}/{k}", "must be null unless status is ok")
        if ok and check[k] is None and k not in optional:
            raise SummaryError(f"{path}/{k}", "required when status is ok")


def validate(doc) -> dict:
    top = _obj(doc, "", TOP_KEYS)
    if top["schema"] != SCHEMA:
        raise SummaryError("/schema", "unsupported schema")
    _str(top["generated_at"], "/generated_at", GENERATED_AT, nullable=False)
    accounts = top["accounts"]
    if type(accounts) is not list:
        raise SummaryError("/accounts", "expected an array")
    if len(accounts) > MAX_ACCOUNTS:
        raise SummaryError("/accounts", "too many items")
    seen = set()
    for i, a in enumerate(accounts):
        p = f"/accounts/{i}"
        _obj(a, p, ACCOUNT_KEYS)
        ref = _str(a["account"], f"{p}/account", REF, nullable=False)
        if ref in seen:
            raise SummaryError(f"{p}/account", "duplicate")
        seen.add(ref)
        _one_of(a["provider"], f"{p}/provider", PROVIDERS)
        _one_of(a["env"], f"{p}/env", ENVS)
        _one_of(a["credential"], f"{p}/credential", CREDENTIALS)

        al = _obj(a["alarms"], f"{p}/alarms", ALARM_KEYS)
        _one_of(al["status"], f"{p}/alarms/status", STATUSES)
        for k in ("firing", "stuck_24h"):
            _int(al[k], f"{p}/alarms/{k}", 0, MAX_COUNT)
        _numbers_follow_status(al, f"{p}/alarms", ("firing", "stuck_24h"))

        sp = _obj(a["spend"], f"{p}/spend", SPEND_KEYS)
        _one_of(sp["status"], f"{p}/spend/status", STATUSES)
        _bool(sp["cached"], f"{p}/spend/cached")
        _one_of(sp["currency"], f"{p}/spend/currency", CURRENCIES)
        _str(sp["as_of"], f"{p}/spend/as_of", DAY)
        for k in ("this_week_cents", "last_week_cents"):
            _int(sp[k], f"{p}/spend/{k}", -MAX_CENTS, MAX_CENTS)
        _numbers_follow_status(sp, f"{p}/spend", ("currency", "as_of", "this_week_cents", "last_week_cents"))

        ce = _obj(a["certs"], f"{p}/certs", CERT_KEYS)
        _one_of(ce["status"], f"{p}/certs/status", STATUSES)
        for k in ("total", "in_use", "expired", "expiring_14d", "expiring_30d", "manual_renewal_30d"):
            _int(ce[k], f"{p}/certs/{k}", 0, MAX_COUNT)
        _int(ce["min_days_left"], f"{p}/certs/min_days_left", -MAX_DAYS, MAX_DAYS)
        _bool(ce["truncated"], f"{p}/certs/truncated")
        _numbers_follow_status(ce, f"{p}/certs",
                               ("total", "in_use", "expired", "expiring_14d", "expiring_30d",
                                "manual_renewal_30d", "min_days_left"), optional=("min_days_left",))

        orph = _obj(a["orphans"], f"{p}/orphans", ORPHAN_KEYS)
        _one_of(orph["status"], f"{p}/orphans/status", STATUSES)
        _int(orph["count"], f"{p}/orphans/count", 0, MAX_COUNT)
        _numbers_follow_status(orph, f"{p}/orphans", ("count",))
    return doc
