"""Read-only boto3 clients, built by dawnfix-core's public guard.

Every API operation the sweeper may make is listed below, per service. ``make_client``
hands that service's list to ``dawnfix_core.awsguard.make_client``, whose guard refuses
anything else at the first event of the call (``provide-client-params``, before botocore
builds the request and before a Stubber answers). A service not listed here is refused
outright. ``iam/sweeper-read-only-policy.json`` grants exactly these actions (a test keeps
the two equal).
"""
from __future__ import annotations

from dawnfix_core.awsguard import ReadOnlyViolation
from dawnfix_core.awsguard import make_client as _guarded_client

__all__ = ["IAM_PREFIX", "NEEDS_NO_PERMISSION", "READ_ONLY_OPERATIONS", "ReadOnlyViolation", "iam_actions",
           "make_client"]

# Every API call the sweeper may make. Anything else is refused before it is built.
READ_ONLY_OPERATIONS: dict[str, frozenset[str]] = {
    "sts": frozenset({"GetCallerIdentity"}),
    "ec2": frozenset({"DescribeVolumes", "DescribeAddresses", "DescribeSnapshots", "DescribeImages",
                      "DescribeInstances", "DescribeNatGateways"}),
    "elbv2": frozenset({"DescribeLoadBalancers", "DescribeTargetGroups", "DescribeTargetHealth",
                        "DescribeTags"}),
    "elb": frozenset({"DescribeLoadBalancers", "DescribeInstanceHealth", "DescribeTags"}),
    "elasticbeanstalk": frozenset({"DescribeEnvironments", "DescribeApplications",
                                   "DescribeEnvironmentResources", "ListTagsForResource"}),
    "ecs": frozenset({"ListClusters", "ListServices", "DescribeServices"}),
    "route53": frozenset({"ListHostedZones", "ListResourceRecordSets"}),
    "logs": frozenset({"DescribeLogGroups", "DescribeLogStreams", "ListTagsForResource"}),
    # NAT gateway traffic and RDS connections since the cutover: one call per region each.
    "cloudwatch": frozenset({"GetMetricData"}),
    "rds": frozenset({"DescribeDBInstances", "DescribeDBSnapshots"}),
}

# boto3 service name -> IAM action prefix, where they differ.
IAM_PREFIX = {"elbv2": "elasticloadbalancing", "elb": "elasticloadbalancing"}
# sts:GetCallerIdentity needs no IAM permission.
NEEDS_NO_PERMISSION = frozenset({"sts:GetCallerIdentity"})


def iam_actions() -> set[str]:
    """The IAM actions the allowlist needs (what iam/sweeper-read-only-policy.json grants)."""
    acts = {f"{IAM_PREFIX.get(s, s)}:{op}" for s, ops in READ_ONLY_OPERATIONS.items() for op in ops}
    return {a for a in acts if a not in NEEDS_NO_PERMISSION}


def make_client(session, service: str, region: str | None):
    """A client that may call only ``READ_ONLY_OPERATIONS[service]``; any other service is refused."""
    if service not in READ_ONLY_OPERATIONS:
        raise ReadOnlyViolation(f"sweeper is read-only; refused service {service}", service=service)
    return _guarded_client(session, service, region, allowed=READ_ONLY_OPERATIONS[service])
