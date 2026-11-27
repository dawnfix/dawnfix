"""boto3 clients that can only make the calls they were built for.

Public API (also re-exported from ``dawnfix_core.sources.aws``)::

    from dawnfix_core.awsguard import ReadOnlyViolation, make_client

    logs = make_client(session, "logs", "eu-central-1")                 # per-service default
    sts = make_client(session, "sts", None, allowed={"GetCallerIdentity"})

Every client gets one guard, registered first on two botocore events:

- ``provide-client-params``: the first event of every API call, before botocore's own
  handlers and before a ``Stubber`` answers, so a refused call never reaches the
  parameter builder, the signer or the network.
- ``before-parameter-build``: the event the guard used before; kept so a handler
  chain that skips the first event still meets the guard.

An operation outside the client's allowlist raises ``ReadOnlyViolation``. A service with
no default allowlist and no ``allowed`` refuses every call: nothing is allowed by
omission.
"""
from __future__ import annotations

from collections.abc import Iterable

GUARD_EVENTS = ("provide-client-params", "before-parameter-build")

# What dawnfix-core's own AWS source calls, per boto3 service name.
DEFAULT_ALLOWED: dict[str, frozenset[str]] = {
    "logs": frozenset({"FilterLogEvents"}),
    "cloudwatch": frozenset({"DescribeAlarms", "GetMetricData"}),
    "elbv2": frozenset({"DescribeLoadBalancers", "DescribeTargetGroups"}),
}

# The union, kept for callers of the earlier single allowlist.
READ_ONLY_OPERATIONS: frozenset[str] = frozenset().union(*DEFAULT_ALLOWED.values())


class ReadOnlyViolation(RuntimeError):
    """An AWS call outside the client's allowlist was refused before it was built.

    ``service`` and ``operation`` name the refused call (``ssm``, ``PutParameter``) so a
    caller can word its own message; both are ``None`` when raised by other code.
    """

    def __init__(self, message: str = "", *, service: str | None = None, operation: str | None = None):
        super().__init__(message)
        self.service = service
        self.operation = operation


def allowed_for(service: str, allowed: Iterable[str] | None = None) -> frozenset[str]:
    """The allowlist a client for ``service`` gets: ``allowed`` if given, else the default."""
    if allowed is not None:
        if isinstance(allowed, str):
            raise TypeError("allowed must be a collection of operation names, not a string")
        return frozenset(allowed)
    return DEFAULT_ALLOWED.get(service, frozenset())


def guard_for(service: str, allowed: frozenset[str]):
    def guard(model=None, **_):
        if model is not None and model.name not in allowed:
            raise ReadOnlyViolation(
                f"dawnfix is read-only; refused AWS call {service}:{model.name} "
                "(not in this client's allowlist)",
                service=service,
                operation=model.name,
            )

    return guard


def make_client(session, service: str, region: str | None, allowed: Iterable[str] | None = None,
                *, config=None):
    """A boto3 client from ``session`` that refuses any operation outside its allowlist.

    ``allowed`` is a set of operation names as AWS spells them (``FilterLogEvents``), not
    boto3 method names. ``None`` takes ``DEFAULT_ALLOWED[service]`` (empty for others).
    ``config`` is an optional ``botocore.config.Config`` (user agent, retries), passed to
    ``session.client`` unchanged; it cannot affect the guard.
    """
    ops = allowed_for(service, allowed)
    kwargs = {"region_name": region}
    if config is not None:
        kwargs["config"] = config
    client = session.client(service, **kwargs)
    guard = guard_for(service, ops)
    for event in GUARD_EVENTS:
        client.meta.events.register_first(event, guard, unique_id=f"dawnfix-readonly-{event}")
    return client
