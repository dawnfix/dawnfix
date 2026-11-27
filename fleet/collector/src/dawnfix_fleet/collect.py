"""One collection for one client: every account, every enabled check, one summary document."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from . import SCHEMA
from . import checks as C
from .config import Account, Client
from .guard import ReadOnlyViolation
from .summary import empty_alarms, empty_certs, empty_spend, orphans_placeholder, validate


def account_ref(client_slug: str, account: Account) -> str:
    """Stable per (client, provider, account). AWS account ids are not secrets; this keeps
    them, and anything that could be joined on them, off the board anyway."""
    raw = f"{client_slug}:{account.provider}:{account.account_id}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def _run(fn, empty):
    try:
        return fn()
    except ReadOnlyViolation:
        raise
    except Exception as e:  # noqa: BLE001 - only the code becomes an enum
        return empty(C.check_status(e))


def collect_account(client_slug: str, account: Account, *, base_session, now: datetime,
                    cache_dir: Path | None, spend_enabled: bool = True,
                    session_factory=None, environ=None) -> dict:
    ref = account_ref(client_slug, account)
    kwargs = {}
    if session_factory is not None:
        kwargs["session_factory"] = session_factory
    if environ is not None:
        kwargs["environ"] = environ
    credential, opened = C.open_account(account, base_session, **kwargs)
    out = {
        "account": ref,
        "provider": account.provider,
        "env": account.env,
        "credential": credential,
        "alarms": empty_alarms("skipped"),
        "spend": empty_spend("skipped"),
        "certs": empty_certs("skipped"),
        "orphans": orphans_placeholder(),
    }
    if opened is None:
        return out
    if "alarms" in account.checks:
        out["alarms"] = _run(lambda: C.alarms(opened, account.regions, now), empty_alarms)
    if "certs" in account.checks:
        out["certs"] = _run(lambda: C.certs(opened, account.regions, now), empty_certs)
    if "spend" in account.checks and spend_enabled:
        out["spend"] = _run(lambda: C.spend(opened, ref, C.utc_today(now), cache_dir), empty_spend)
    return out


def collect(client: Client, *, base_session, now: datetime | None = None, cache_dir: Path | None = None,
            spend_enabled: bool = True, session_factory=None, environ=None) -> dict:
    now = now or datetime.now(timezone.utc)
    doc = {
        "schema": SCHEMA,
        "generated_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "accounts": [
            collect_account(client.slug, a, base_session=base_session, now=now, cache_dir=cache_dir,
                            spend_enabled=spend_enabled, session_factory=session_factory, environ=environ)
            for a in client.accounts
        ],
    }
    return validate(doc)
