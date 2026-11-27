"""Read-only boto3 clients, built by dawnfix-core's public guard.

Receipt makes one kind of AWS call: Cost Explorer ``GetCostAndUsage`` ($0.01 per request,
counted in every comment). ``make_client`` hands that allowlist to
``dawnfix_core.awsguard.make_client``, which refuses anything else at the first event of
the call, before botocore builds the request. Any other service is refused outright.
``iam/receipt-ce-read-policy.json`` grants exactly this (a test keeps the two equal).
"""
from __future__ import annotations

from dawnfix_core.awsguard import ReadOnlyViolation
from dawnfix_core.awsguard import make_client as _guarded_client

__all__ = ["READ_ONLY_OPERATIONS", "ReadOnlyViolation", "iam_actions", "make_client"]

READ_ONLY_OPERATIONS: dict[str, frozenset[str]] = {
    "ce": frozenset({"GetCostAndUsage"}),
}


def iam_actions() -> set[str]:
    return {f"{s}:{op}" for s, ops in READ_ONLY_OPERATIONS.items() for op in ops}


def make_client(session, service: str, region: str | None = "us-east-1"):
    """A client that may call only ``READ_ONLY_OPERATIONS[service]``; any other service is refused."""
    if service not in READ_ONLY_OPERATIONS:
        raise ReadOnlyViolation(f"receipt is read-only; refused service {service}", service=service)
    return _guarded_client(session, service, region, allowed=READ_ONLY_OPERATIONS[service])
