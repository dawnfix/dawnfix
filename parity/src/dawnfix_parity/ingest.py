"""The `dawnfix.parity/1` document: what `parity check --ingest-out` writes and the CI
workflow sends to the hosted service (only with an Enterprise key). Counts, enums and one
hashed pair id; never a key name, a parameter or secret name, an ARN, an account id, an environment name or a value.
The shape is `schema/parity-ingest.schema.json` (closed objects); a test validates every
document built here against it.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .diff import FINDING_KINDS, DiffResult
from .inventory import INVENTORY_FLAGS, Row

SCHEMA = "dawnfix.parity/1"
MAX_COUNT = 1_000_000


def pair_id(left: str, right: str) -> str:
    """Stable id of an environment pair. Env names are low-entropy: an id, not a secret."""
    return hashlib.sha256(f"{SCHEMA}\0{left}\0{right}".encode()).hexdigest()[:16]


def _n(x: int) -> int:
    return max(0, min(int(x), MAX_COUNT))


def build_ingest(res: DiffResult, failing: int, rows: dict[str, list[Row]] | None, now: datetime,
                 allowed_flag=lambda flag, row: False) -> dict:
    findings = {k: 0 for k in FINDING_KINDS}
    allowed = 0
    for f in res.findings:
        if f.allowed:
            allowed += 1
        else:
            findings[f.kind] += 1
    inventory = None
    if rows is not None:
        flags = {k: 0 for k in INVENTORY_FLAGS}
        items = 0
        for env_rows in rows.values():
            for r in env_rows:
                items += 1
                for flag in r.flags:
                    if flag in flags and not allowed_flag(flag, r):
                        flags[flag] += 1
        inventory = {"items": _n(items), "flags": {k: _n(v) for k, v in flags.items()}}
    return {
        "schema": SCHEMA,
        "generated_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pair": pair_id(res.left, res.right),
        "hashed": bool(res.hashed),
        "result": "drift" if failing else "pass",
        "keys": {"left": _n(res.counts.get("keys_left", 0)), "right": _n(res.counts.get("keys_right", 0)),
                 "references": _n(res.counts.get("references", 0))},
        "findings": {k: _n(v) for k, v in findings.items()},
        "allowed": _n(allowed),
        "failing": _n(failing),
        "inventory": inventory,
    }
