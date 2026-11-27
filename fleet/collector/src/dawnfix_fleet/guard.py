"""Every AWS call the collector may make, per service. Anything else is refused before it is built.

The guard itself is dawnfix-core's public one (``dawnfix_core.awsguard.make_client``):
registered first on ``provide-client-params`` (botocore's first event for a call, before
parameters are built, validated or stubbed) and on ``before-parameter-build``, so a refused
operation never reaches the network whatever the role would have allowed. This module only
says which operations, per service, and refuses any other service outright.
"""
from __future__ import annotations

from dawnfix_core.awsguard import ReadOnlyViolation
from dawnfix_core.awsguard import make_client as _guarded_client

__all__ = ["CLIENT_ROLE_ACTIONS", "READ_ONLY_OPERATIONS", "ReadOnlyViolation", "make_client"]

READ_ONLY_OPERATIONS: dict[str, frozenset[str]] = {
    # The agency's own side: hop into the client's account, or check whose credentials these are.
    "sts": frozenset({"AssumeRole", "GetCallerIdentity"}),
    "cloudwatch": frozenset({"DescribeAlarms"}),
    # $0.01 per request: called at most once per account per UTC day (see spend.py).
    "ce": frozenset({"GetCostAndUsage"}),
    "acm": frozenset({"ListCertificates", "DescribeCertificate"}),
}

# What the client's role must grant (sts is the caller's side, not the client's role).
# fleet/infra/tests checks the CloudFormation policy grants exactly this and nothing else,
# and infra/aws/verify_readonly.py --profile fleet uses it as the required set.
CLIENT_ROLE_ACTIONS = frozenset({
    "cloudwatch:DescribeAlarms",
    "ce:GetCostAndUsage",
    "acm:ListCertificates",
    "acm:DescribeCertificate",
})


def make_client(session, service: str, region: str):
    """A client that may call only ``READ_ONLY_OPERATIONS[service]``; any other service is refused."""
    if service not in READ_ONLY_OPERATIONS:
        raise ReadOnlyViolation(f"fleet is read-only; refused service {service}", service=service)
    return _guarded_client(session, service, region, allowed=READ_ONLY_OPERATIONS[service])
