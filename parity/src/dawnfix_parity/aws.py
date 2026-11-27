"""boto3 clients that can only read, built by dawnfix-core's public guard.

Every API operation parity may call is listed below, per service; ``make_client`` hands
that service's list to ``dawnfix_core.awsguard.make_client``, whose guard refuses
anything else at the first event of the call (``provide-client-params``, before botocore
builds the request and before a Stubber answers), so a bug cannot turn into a write.
"""
from __future__ import annotations

from dawnfix_core.awsguard import ReadOnlyViolation
from dawnfix_core.awsguard import make_client as _guarded_client

from . import brand

__all__ = ["READ_ONLY_OPERATIONS", "SERVICE_OPERATIONS", "VALUE_OPERATIONS", "AwsError", "EnvAws",
           "ReadOnlyViolation", "error_code", "make_client"]

# operation -> why it is needed. Value-reading calls are only made with --compare-hashes.
READ_ONLY_OPERATIONS = {
    "DescribeParameters": "SSM parameter names, types, versions, dates (no values)",
    "GetParameters": "SSM values, --compare-hashes only (hashed in memory, never kept)",
    "ListSecrets": "Secrets Manager names, rotation, last changed/accessed (no values)",
    "DescribeSecret": "existence check for a secret referenced outside the listed prefixes",
    "GetSecretValue": "secret values, --compare-hashes only (hashed in memory, never kept)",
    "ListServices": "ECS services in a cluster",
    "DescribeServices": "ECS service -> current task definition",
    "DescribeTaskDefinition": "container environment and secrets/valueFrom",
    "ListFunctions": "Lambda names and environment variables",
    "LookupEvents": "CloudTrail who-reads-what, --cloudtrail only",
    "GetCallerIdentity": "account id of each environment",
    "AssumeRole": "per-environment read-only role from .parity.yml role_arn",
}
VALUE_OPERATIONS = frozenset({"GetParameters", "GetSecretValue"})

# Each client gets only its own service's operations (stricter than one shared list).
SERVICE_OPERATIONS: dict[str, frozenset[str]] = {
    "ssm": frozenset({"DescribeParameters", "GetParameters"}),
    "secretsmanager": frozenset({"ListSecrets", "DescribeSecret", "GetSecretValue"}),
    "ecs": frozenset({"ListServices", "DescribeServices", "DescribeTaskDefinition"}),
    "lambda": frozenset({"ListFunctions"}),
    "cloudtrail": frozenset({"LookupEvents"}),
    "sts": frozenset({"GetCallerIdentity", "AssumeRole"}),
}
assert frozenset().union(*SERVICE_OPERATIONS.values()) == frozenset(READ_ONLY_OPERATIONS)


class AwsError(RuntimeError):
    """An AWS call failed; carries the error code only (messages can echo input)."""

    def __init__(self, code: str, where: str = ""):
        super().__init__(f"{where}: {code}" if where else code)
        self.code = code


def make_client(session, service: str, region: str | None):
    """A guarded client: refuses every operation not in ``SERVICE_OPERATIONS[service]``
    (an unknown service gets an empty list, so every call is refused)."""
    from botocore.config import Config

    cfg = Config(user_agent_extra=brand.USER_AGENT_EXTRA, retries={"mode": "standard", "max_attempts": 5})
    return _guarded_client(session, service, region, allowed=SERVICE_OPERATIONS.get(service, frozenset()),
                           config=cfg)


def refused(e: ReadOnlyViolation) -> str:
    """parity's own wording for a refused call (the core's message names dawnfix)."""
    op = getattr(e, "operation", None) or "?"
    return f"{brand.PRODUCT_NAME} is read-only; refused AWS call {op}"


def error_code(e: Exception) -> str:
    resp = getattr(e, "response", None)
    if isinstance(resp, dict):
        return resp.get("Error", {}).get("Code") or type(e).__name__
    return type(e).__name__


class EnvAws:
    """Clients for one environment. Tests pass `clients={(service, region): stubbed_client}`."""

    def __init__(self, env, session=None, clients: dict | None = None):
        self.env = env
        self._session = session
        self._clients = dict(clients or {})

    def session(self):
        if self._session is None:
            import boto3

            base = boto3.session.Session(profile_name=self.env.profile, region_name=self.env.region)
            if self.env.role_arn:
                sts = make_client(base, "sts", self.env.region)
                c = sts.assume_role(RoleArn=self.env.role_arn, RoleSessionName=brand.ASSUME_ROLE_SESSION,
                                    DurationSeconds=3600)["Credentials"]
                base = boto3.session.Session(
                    aws_access_key_id=c["AccessKeyId"], aws_secret_access_key=c["SecretAccessKey"],
                    aws_session_token=c["SessionToken"], region_name=self.env.region)
            self._session = base
        return self._session

    def client(self, service: str, region: str | None = None):
        key = (service, region or self.env.region)
        if key not in self._clients:
            self._clients[key] = make_client(self.session(), service, key[1])
        return self._clients[key]
