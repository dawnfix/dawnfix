"""Read-only boto3 clients, built by dawnfix-core's public guard.

Every API operation Leastpriv may make is listed below, per service. ``make_client`` hands
that service's list to ``dawnfix_core.awsguard.make_client``, which refuses anything else
at the first event of the call, before botocore builds the request. Any other service is
refused outright. ``iam/leastpriv-read-only-policy.json`` grants exactly these actions (a
test keeps the two equal).

GenerateServiceLastAccessedDetails starts a report job; it changes no IAM entity and is
granted by AWS's IAMReadOnlyAccess (iam:Generate*). Access Analyzer's
GenerateFindingRecommendation is deliberately not allowed: we compute the policy ourselves.
"""
from __future__ import annotations

from dawnfix_core.awsguard import ReadOnlyViolation
from dawnfix_core.awsguard import make_client as _guarded_client

__all__ = ["IAM_PREFIX", "READ_ONLY_OPERATIONS", "ReadOnlyViolation", "iam_actions", "make_client"]

READ_ONLY_OPERATIONS: dict[str, frozenset[str]] = {
    "iam": frozenset({"GetRole", "ListAttachedRolePolicies", "GetPolicy", "GetPolicyVersion",
                      "ListRolePolicies", "GetRolePolicy",
                      "GenerateServiceLastAccessedDetails", "GetServiceLastAccessedDetails"}),
    "accessanalyzer": frozenset({"ListAnalyzers", "ListFindingsV2", "GetFindingV2"}),
}

# boto3 service name -> IAM action prefix, where they differ.
IAM_PREFIX = {"accessanalyzer": "access-analyzer"}


def iam_actions() -> set[str]:
    """The IAM actions the allowlist needs (what iam/leastpriv-read-only-policy.json grants)."""
    return {f"{IAM_PREFIX.get(s, s)}:{op}" for s, ops in READ_ONLY_OPERATIONS.items() for op in ops}


def make_client(session, service: str, region: str | None):
    """A client that may call only ``READ_ONLY_OPERATIONS[service]``; any other service is refused."""
    if service not in READ_ONLY_OPERATIONS:
        raise ReadOnlyViolation(f"leastpriv is read-only; refused service {service}", service=service)
    return _guarded_client(session, service, region, allowed=READ_ONLY_OPERATIONS[service])
