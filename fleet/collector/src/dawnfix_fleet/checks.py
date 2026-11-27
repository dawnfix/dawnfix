"""The read-only checks: getting into the account, alarms in ALARM, certificate expiry, spend.

Each returns numbers and enums only. AWS error messages can echo input (ARNs, names), so
only the error *code* is ever looked at, and only to pick an enum.
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from .config import Account
from .guard import make_client

MAX_PAGES = 50
MAX_DESCRIBE = 200
DAY = timedelta(days=1)
CURRENCIES = ("USD", "EUR", "GBP", "CHF", "CAD", "AUD", "JPY")
# Cost Explorer lives in us-east-1 for the aws partition, whatever the account's regions.
CE_REGION = "us-east-1"
# Usage spend: credits and refunds would make a quiet week look like a saving.
CE_FILTER = {"Not": {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", "Refund"]}}}
EXTERNAL_ID = re.compile(r"^[\w+=,.@:/-]{2,1224}$")
SESSION_NAME = "fleet-collect"
SESSION_SECONDS = 900

DENIED = {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation", "UnauthorizedException",
          "InvalidClientTokenId", "UnrecognizedClientException", "SignatureDoesNotMatch",
          "AuthFailure", "OptInRequired"}
EXPIRED = {"ExpiredToken", "ExpiredTokenException", "RequestExpired", "TokenRefreshRequired",
           "NoCredentialsError", "UnauthorizedSSOTokenError", "SSOTokenLoadError"}
THROTTLED = {"Throttling", "ThrottlingException", "TooManyRequestsException", "RequestLimitExceeded",
             "LimitExceededException"}


def error_code(e: Exception) -> str:
    resp = getattr(e, "response", None)
    if isinstance(resp, dict):
        return resp.get("Error", {}).get("Code") or type(e).__name__
    return type(e).__name__


def classify(e: Exception) -> str:
    code = error_code(e)
    if code in DENIED:
        return "denied"
    if code in EXPIRED:
        return "expired"
    if code in THROTTLED:
        return "throttled"
    return "error"


def check_status(e: Exception) -> str:
    """A check's status: expired credentials mid-run are an error for that check."""
    s = classify(e)
    return s if s in ("denied", "throttled") else "error"


class Opened:
    """An account we got into: a session plus guarded clients, created once per (service, region)."""

    def __init__(self, session):
        self.session = session
        self._clients: dict[tuple[str, str], object] = {}

    def client(self, service: str, region: str):
        key = (service, region)
        if key not in self._clients:
            self._clients[key] = make_client(self.session, service, region)
        return self._clients[key]


def _session_from(creds: dict):
    import boto3

    return boto3.session.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )


def open_account(account: Account, base_session, session_factory=_session_from,
                 environ=os.environ) -> tuple[str, Opened | None]:
    """(credential status, opened account or None). Never raises for AWS reasons."""
    sts = make_client(base_session, "sts", account.regions[0])
    try:
        if account.assume:
            external_id = environ.get(account.external_id_env or "", "")
            if not EXTERNAL_ID.match(external_id):
                # Missing or malformed: say so locally, by variable name only.
                print(f"fleet: {account.external_id_env} is not set to a valid External ID", file=_stderr())
                return "error", None
            resp = sts.assume_role(
                RoleArn=account.role_arn,
                RoleSessionName=SESSION_NAME,
                ExternalId=external_id,
                DurationSeconds=SESSION_SECONDS,
            )
            got = resp["AssumedRoleUser"]["Arn"].split(":")[4]
            if got != account.account_id:
                return "account_mismatch", None
            return "ok", Opened(session_factory(resp["Credentials"]))
        # The client's own CI: credentials are already this account's (OIDC). Make sure.
        ident = sts.get_caller_identity()
        if ident.get("Account") != account.account_id:
            return "account_mismatch", None
        return "ok", Opened(base_session)
    except Exception as e:  # noqa: BLE001 - mapped to an enum, message dropped
        return classify(e), None


def _stderr():
    import sys

    return sys.stderr


def alarms(opened: Opened, regions, now: datetime) -> dict:
    firing = stuck = 0
    for region in regions:
        cw = opened.client("cloudwatch", region)
        token = None
        for _ in range(MAX_PAGES):
            params = {"StateValue": "ALARM", "AlarmTypes": ["MetricAlarm", "CompositeAlarm"], "MaxRecords": 100}
            if token:
                params["NextToken"] = token
            resp = cw.describe_alarms(**params)
            for a in [*resp.get("MetricAlarms", []), *resp.get("CompositeAlarms", [])]:
                firing += 1
                ts = a.get("StateUpdatedTimestamp")
                if isinstance(ts, datetime) and now - ts > DAY:
                    stuck += 1
            token = resp.get("NextToken")
            if not token:
                break
    return {"status": "ok", "firing": min(firing, 1_000_000), "stuck_24h": min(stuck, 1_000_000)}


def certs(opened: Opened, regions, now: datetime) -> dict:
    arns: list[tuple[str, str]] = []
    for region in regions:
        acm = opened.client("acm", region)
        token = None
        for _ in range(MAX_PAGES):
            params = {"CertificateStatuses": ["ISSUED", "EXPIRED"], "MaxItems": 100}
            if token:
                params["NextToken"] = token
            resp = acm.list_certificates(**params)
            arns.extend((region, c["CertificateArn"]) for c in resp.get("CertificateSummaryList", []))
            token = resp.get("NextToken")
            if not token:
                break

    truncated = len(arns) > MAX_DESCRIBE
    total = in_use = expired = exp14 = exp30 = manual30 = 0
    min_days: int | None = None
    for region, arn in arns[:MAX_DESCRIBE]:
        c = opened.client("acm", region).describe_certificate(CertificateArn=arn)["Certificate"]
        total += 1
        not_after = c.get("NotAfter")
        if not c.get("InUseBy") or not isinstance(not_after, datetime):
            continue
        in_use += 1
        days = math.floor((not_after - now).total_seconds() / 86400)
        min_days = days if min_days is None else min(min_days, days)
        if days < 0:
            expired += 1
        if 0 <= days <= 14:
            exp14 += 1
        if 0 <= days <= 30:
            exp30 += 1
        auto = c.get("Type") == "AMAZON_ISSUED" and c.get("RenewalEligibility") == "ELIGIBLE"
        if days <= 30 and not auto:
            manual30 += 1
    if min_days is not None:
        min_days = max(-36500, min(36500, min_days))
    return {"status": "ok", "total": total, "in_use": in_use, "expired": expired, "expiring_14d": exp14,
            "expiring_30d": exp30, "manual_renewal_30d": manual30, "min_days_left": min_days,
            "truncated": truncated}


# --- spend -------------------------------------------------------------------------------

class SpendError(RuntimeError):
    pass


def _cache_path(cache_dir: Path, ref: str) -> Path:
    return cache_dir / f"spend-{ref}.json"


def read_cache(cache_dir: Path | None, ref: str, today: date) -> dict | None:
    if cache_dir is None:
        return None
    try:
        doc = json.loads(_cache_path(cache_dir, ref).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("day") != today.isoformat():
        return None
    try:
        out = {
            "currency": doc["currency"],
            "as_of": doc["as_of"],
            "this_week_cents": doc["this_week_cents"],
            "last_week_cents": doc["last_week_cents"],
        }
    except KeyError:
        return None
    if out["currency"] not in (*CURRENCIES, "OTHER") or not isinstance(out["as_of"], str):
        return None
    if not all(type(out[k]) is int for k in ("this_week_cents", "last_week_cents")):
        return None
    return out


def write_cache(cache_dir: Path | None, ref: str, today: date, value: dict) -> None:
    if cache_dir is None:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_path(cache_dir, ref).write_text(json.dumps({"day": today.isoformat(), **value}, sort_keys=True))


def _cents(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def spend(opened: Opened, ref: str, today: date, cache_dir: Path | None) -> dict:
    """Last 7 whole UTC days against the 7 before. One Cost Explorer request per account per day."""
    cached = read_cache(cache_dir, ref, today)
    if cached is not None:
        return {"status": "ok", "cached": True, **cached}

    ce = opened.client("ce", CE_REGION)
    start, end, split = today - 14 * DAY, today, today - 7 * DAY
    this_week = last_week = Decimal(0)
    units: set[str] = set()
    token = None
    for _ in range(5):
        params = {
            "TimePeriod": {"Start": start.isoformat(), "End": end.isoformat()},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost"],
            "Filter": CE_FILTER,
        }
        if token:
            params["NextPageToken"] = token
        resp = ce.get_cost_and_usage(**params)
        for r in resp.get("ResultsByTime", []):
            day = date.fromisoformat(r["TimePeriod"]["Start"])
            total = r.get("Total", {}).get("UnblendedCost", {})
            try:
                amount = Decimal(total.get("Amount", "0"))
            except InvalidOperation:
                raise SpendError("amount") from None
            if not amount.is_finite():
                raise SpendError("amount")
            if amount != 0 and total.get("Unit"):
                units.add(total["Unit"])
            if day >= split:
                this_week += amount
            else:
                last_week += amount
        token = resp.get("NextPageToken")
        if not token:
            break
    if len(units) > 1:
        raise SpendError("mixed currencies")
    unit = next(iter(units), "USD")
    value = {
        "currency": unit if unit in CURRENCIES else "OTHER",
        "as_of": (today - DAY).isoformat(),
        "this_week_cents": _cents(this_week),
        "last_week_cents": _cents(last_week),
    }
    write_cache(cache_dir, ref, today, value)
    return {"status": "ok", "cached": False, **value}


def utc_today(now: datetime) -> date:
    return now.astimezone(timezone.utc).date()
