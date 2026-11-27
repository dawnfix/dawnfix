#!/usr/bin/env python3
"""Verify that a Dawnfix AWS role is read-only before the workflow is allowed to use it.

    python verify_readonly.py arn:aws:iam::123456789012:role/dawnfix-read \
        [--log-group my-api-prod ...] [--region us-east-1] [--aws-profile admin] [--json]
    python verify_readonly.py arn:aws:iam::123456789012:role/fleet-read --profile fleet

`--profile` picks which role is being checked (default `dawnfix`, the error-log read role;
`fleet`, the agency board's per-client read role, whose required set is exactly what the
board's collector calls). The caller's AWS credentials profile is `--aws-profile`; an
older `--profile <aws profile>` that names no role profile is still taken as that, with a
note on stderr.

Run it with the customer's own (admin) credentials, not the role's. Three checks:

1. Simulation (iam:SimulatePrincipalPolicy, includes permission boundaries and SCPs):
   every write or secret-reading action in WRITE_ACTIONS must be denied, against "*" and
   against each given log group; every action in REQUIRED_READ_ACTIONS (what
   dawnfix-core calls) must be allowed.
2. Policy scan: every Allow statement in the role's inline and attached policies may only
   grant actions inside READ_ONLY_PATTERNS. The simulator matches resources literally, so a
   grant such as s3:PutObject on one bucket would not show up against "*"; this catches it.
3. Trust policy: if GitHub OIDC is trusted, the statement must pin `aud` and `sub`.

Exit 0 when the role passes, 1 when it does not, 2 on usage or AWS errors.
Caller needs iam:SimulatePrincipalPolicy, iam:GetRole, iam:ListRolePolicies,
iam:GetRolePolicy, iam:ListAttachedRolePolicies, iam:GetPolicy, iam:GetPolicyVersion.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
import urllib.parse
from dataclasses import dataclass, field

ROLE_ARN = re.compile(r"^arn:(aws[a-z-]*):iam::(\d{12}):role/(?:[\w+=,.@-]+/)*([\w+=,.@-]+)$")
GITHUB_OIDC = "token.actions.githubusercontent.com"

# What dawnfix-core actually calls (core/src/dawnfix_core/sources/aws.py). Must be allowed.
REQUIRED_READ_ACTIONS = (
    "logs:FilterLogEvents",
    "cloudwatch:DescribeAlarms",
    "cloudwatch:GetMetricData",
    "elasticloadbalancing:DescribeLoadBalancers",
    "elasticloadbalancing:DescribeTargetGroups",
)
# The rest of what infra/aws/dawnfix-read-role.yaml grants. Reported if denied, not fatal.
EXPECTED_READ_ACTIONS = (
    "logs:GetLogEvents",
    "logs:StartQuery",
    "logs:StopQuery",
    "logs:GetQueryResults",
    "logs:DescribeLogGroups",
    "cloudwatch:GetMetricStatistics",
    "cloudwatch:ListMetrics",
    "elasticloadbalancing:DescribeTargetHealth",
)
# Log actions that are scoped to log groups by the template; simulated per log group.
LOG_GROUP_SCOPED = {"logs:FilterLogEvents", "logs:GetLogEvents", "logs:StartQuery"}

# Must be denied. Writes, plus reads of data that has nothing to do with error logs.
# IAM wildcards cannot be simulated, so "iam:*" is covered by a sample of its dangerous actions.
WRITE_ACTIONS = (
    "logs:DeleteLogGroup", "logs:DeleteLogStream", "logs:CreateLogGroup", "logs:PutLogEvents",
    "logs:PutRetentionPolicy", "logs:PutSubscriptionFilter", "logs:PutMetricFilter",
    "logs:PutResourcePolicy", "logs:CreateExportTask", "logs:AssociateKmsKey",
    "logs:DisassociateKmsKey", "logs:TagResource",
    "cloudwatch:PutMetricAlarm", "cloudwatch:DeleteAlarms", "cloudwatch:SetAlarmState",
    "cloudwatch:DisableAlarmActions", "cloudwatch:PutMetricData", "cloudwatch:PutDashboard",
    "elasticloadbalancing:DeleteLoadBalancer", "elasticloadbalancing:ModifyListener",
    "elasticloadbalancing:RegisterTargets", "elasticloadbalancing:DeregisterTargets",
    "iam:CreateUser", "iam:CreateAccessKey", "iam:CreateRole", "iam:DeleteRole",
    "iam:AttachRolePolicy", "iam:PutRolePolicy", "iam:UpdateAssumeRolePolicy", "iam:PassRole",
    "sts:AssumeRole",
    "s3:PutObject", "s3:DeleteObject", "s3:GetObject", "s3:PutBucketPolicy",
    "ec2:TerminateInstances", "ec2:RunInstances", "ec2:AuthorizeSecurityGroupIngress",
    "lambda:UpdateFunctionCode", "lambda:InvokeFunction",
    "ecs:UpdateService", "ecs:RunTask",
    "rds:DeleteDBInstance", "dynamodb:DeleteTable", "dynamodb:PutItem",
    "secretsmanager:GetSecretValue", "ssm:GetParameter", "kms:Decrypt",
    "sqs:SendMessage", "sns:Publish",
)

# Allow statements may only use action patterns covered by these (case-insensitive).
READ_ONLY_PATTERNS = (
    "logs:describe*", "logs:get*", "logs:list*", "logs:filterlogevents",
    "logs:startquery", "logs:stopquery", "logs:startlivetail", "logs:stoplivetail",
    "cloudwatch:describe*", "cloudwatch:get*", "cloudwatch:list*",
    "elasticloadbalancing:describe*",
)


# The agency board's per-client read role: exactly the collector's CLIENT_ROLE_ACTIONS (a
# test on the board's side holds the two equal) and nothing else may be granted.
FLEET_REQUIRED_ACTIONS = (
    "cloudwatch:DescribeAlarms",
    "acm:ListCertificates",
    "acm:DescribeCertificate",
    "ce:GetCostAndUsage",
)
FLEET_WRITE_ACTIONS = WRITE_ACTIONS + (
    "acm:DeleteCertificate", "acm:ExportCertificate", "acm:ImportCertificate", "acm:RequestCertificate",
    "ce:CreateAnomalyMonitor", "ce:DeleteAnomalyMonitor", "ce:UpdateCostAllocationTagsStatus",
    "logs:FilterLogEvents", "logs:GetLogEvents", "cloudwatch:GetMetricData",
)
FLEET_READ_ONLY_PATTERNS = tuple(a.lower() for a in FLEET_REQUIRED_ACTIONS)


@dataclass(frozen=True)
class RoleProfile:
    name: str
    required: tuple[str, ...]
    expected: tuple[str, ...]
    writes: tuple[str, ...]
    read_only_patterns: tuple[str, ...]
    log_group_scoped: frozenset[str]
    # Cross-account trust (an AWS principal) must carry an sts:ExternalId condition.
    external_id_required: bool = False


ROLE_PROFILES: dict[str, RoleProfile] = {
    "dawnfix": RoleProfile("dawnfix", REQUIRED_READ_ACTIONS, EXPECTED_READ_ACTIONS, WRITE_ACTIONS,
                             READ_ONLY_PATTERNS, frozenset(LOG_GROUP_SCOPED)),
    "fleet": RoleProfile("fleet", FLEET_REQUIRED_ACTIONS, (), FLEET_WRITE_ACTIONS, FLEET_READ_ONLY_PATTERNS,
                         frozenset(), external_id_required=True),
}
DEFAULT_PROFILE = ROLE_PROFILES["dawnfix"]


class UsageError(Exception):
    pass


@dataclass
class Report:
    role_arn: str
    allowed_writes: list[str] = field(default_factory=list)  # "action on resource"
    denied_required: list[str] = field(default_factory=list)
    denied_expected: list[str] = field(default_factory=list)
    extra_grants: list[str] = field(default_factory=list)  # "policy: action"
    trust_problems: list[str] = field(default_factory=list)
    unchecked: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.allowed_writes or self.denied_required or self.extra_grants or self.trust_problems)

    def as_dict(self) -> dict:
        return {
            "role_arn": self.role_arn,
            "ok": self.ok,
            "allowed_writes": self.allowed_writes,
            "denied_required": self.denied_required,
            "denied_expected": self.denied_expected,
            "extra_grants": self.extra_grants,
            "trust_problems": self.trust_problems,
            "unchecked": self.unchecked,
        }


def parse_role_arn(arn: str) -> tuple[str, str, str]:
    """(partition, account, role name)."""
    m = ROLE_ARN.match(arn or "")
    if not m:
        raise UsageError(f"not an IAM role ARN: {arn!r}")
    return m.group(1), m.group(2), m.group(3)


def log_group_arn(partition: str, region: str, account: str, name: str) -> str:
    return f"arn:{partition}:logs:{region}:{account}:log-group:{name}"


def simulate(iam, role_arn: str, actions, resource: str = "*") -> dict[str, str]:
    """action -> EvalDecision ('allowed', 'explicitDeny', 'implicitDeny')."""
    out: dict[str, str] = {}
    kwargs = {"PolicySourceArn": role_arn, "ActionNames": list(actions), "ResourceArns": [resource]}
    while True:
        resp = iam.simulate_principal_policy(**kwargs)
        for r in resp.get("EvaluationResults", []):
            out[r["EvalActionName"]] = r["EvalDecision"]
        if not resp.get("IsTruncated"):
            return out
        kwargs["Marker"] = resp["Marker"]


def _doc(raw) -> dict:
    """IAM returns policy documents URL-encoded; boto3 usually decodes them already."""
    if isinstance(raw, dict):
        return raw
    return json.loads(urllib.parse.unquote(raw))


def _pages(call, key: str, **kwargs):
    while True:
        resp = call(**kwargs)
        yield from resp.get(key, [])
        if not resp.get("IsTruncated"):
            return
        kwargs["Marker"] = resp["Marker"]


def policy_documents(iam, role_name: str) -> list[tuple[str, dict]]:
    docs = []
    for name in _pages(iam.list_role_policies, "PolicyNames", RoleName=role_name):
        resp = iam.get_role_policy(RoleName=role_name, PolicyName=name)
        docs.append((f"inline:{name}", _doc(resp["PolicyDocument"])))
    for att in _pages(iam.list_attached_role_policies, "AttachedPolicies", RoleName=role_name):
        pol = iam.get_policy(PolicyArn=att["PolicyArn"])["Policy"]
        ver = iam.get_policy_version(PolicyArn=att["PolicyArn"], VersionId=pol["DefaultVersionId"])
        docs.append((f"attached:{att['PolicyName']}", _doc(ver["PolicyVersion"]["Document"])))
    return docs


def _as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def action_is_read_only(pattern: str, allowed_patterns=READ_ONLY_PATTERNS) -> bool:
    p = pattern.lower()
    if allowed_patterns is not READ_ONLY_PATTERNS and any(c in p for c in "*?"):
        # A profile with exact actions only: a wildcard grant is never inside it.
        return False
    return any(fnmatch.fnmatchcase(p, allowed) for allowed in allowed_patterns)


def extra_grants(docs: list[tuple[str, dict]], allowed_patterns=READ_ONLY_PATTERNS) -> list[str]:
    found = []
    for source, doc in docs:
        for st in _as_list(doc.get("Statement")):
            if st.get("Effect") != "Allow":
                continue
            if "NotAction" in st:
                found.append(f"{source}: Allow with NotAction (grants everything not listed)")
                continue
            for action in _as_list(st.get("Action")):
                if not action_is_read_only(action, allowed_patterns):
                    found.append(f"{source}: {action}")
    return found


def trust_problems(trust: dict, external_id_required: bool = False) -> list[str]:
    problems = []
    for st in _as_list(trust.get("Statement")):
        if st.get("Effect") != "Allow":
            continue
        principal = st.get("Principal")
        if principal == "*" or (isinstance(principal, dict) and "*" in _as_list(principal.get("AWS"))):
            problems.append("trust policy allows any principal")
            continue
        if external_id_required and isinstance(principal, dict) and principal.get("AWS"):
            cond = st.get("Condition") or {}
            ids = [v for op, kv in cond.items() if op in ("StringEquals", "StringLike") for k, v in kv.items()
                   if k.lower() == "sts:externalid"]
            if not ids or any(not str(x) or "*" in str(x) for v in ids for x in _as_list(v)):
                problems.append("cross-account trust without an exact sts:ExternalId condition (confused deputy)")
        federated = _as_list(principal.get("Federated")) if isinstance(principal, dict) else []
        if not any(str(f).endswith(f"oidc-provider/{GITHUB_OIDC}") for f in federated):
            continue
        cond = st.get("Condition") or {}
        keys = {}
        for op, kv in cond.items():
            for k, v in kv.items():
                keys.setdefault(k, []).append((op, _as_list(v)))
        if f"{GITHUB_OIDC}:aud" not in keys:
            problems.append("GitHub OIDC trust without an aud condition")
        subs = keys.get(f"{GITHUB_OIDC}:sub")
        if not subs:
            problems.append("GitHub OIDC trust without a sub condition: any GitHub repo could assume it")
            continue
        for op, values in subs:
            for v in values:
                m = re.match(r"^repo:([^/:]+)/([^:]+):", str(v))
                if not m or "*" in m.group(1) or "*" in m.group(2):
                    problems.append(f"sub condition {v!r} ({op}) is not pinned to one repository")
    return problems


def verify(iam, role_arn: str, log_groups=(), region: str = "us-east-1",
           profile: RoleProfile = DEFAULT_PROFILE) -> Report:
    partition, account, role_name = parse_role_arn(role_arn)
    report = Report(role_arn)

    # 1. Simulation.
    all_reads = profile.required + profile.expected
    unscoped_reads = [a for a in all_reads if a not in profile.log_group_scoped]
    decisions = simulate(iam, role_arn, list(profile.writes) + unscoped_reads, "*")
    for a in profile.writes:
        if decisions.get(a) == "allowed":
            report.allowed_writes.append(f"{a} on *")
    for a in unscoped_reads:
        if decisions.get(a) != "allowed":
            (report.denied_required if a in profile.required else report.denied_expected).append(f"{a} on *")

    scoped_reads = [a for a in all_reads if a in profile.log_group_scoped]
    log_writes = [a for a in profile.writes if a.startswith("logs:")]
    if not scoped_reads:
        if log_groups:
            report.unchecked.append(f"--log-group ignored: the {profile.name} role reads no logs")
        log_groups = ()
    elif not log_groups:
        report.unchecked.append(
            "log-group-scoped reads (" + ", ".join(scoped_reads) + "): pass --log-group to check them")
    for name in log_groups:
        arn = log_group_arn(partition, region, account, name)
        d = simulate(iam, role_arn, scoped_reads + log_writes, arn)
        for a in log_writes:
            if d.get(a) == "allowed":
                report.allowed_writes.append(f"{a} on {name}")
        for a in scoped_reads:
            if d.get(a) != "allowed":
                (report.denied_required if a in profile.required else report.denied_expected).append(f"{a} on {name}")

    # 2. Policy scan. 3. Trust.
    report.extra_grants = extra_grants(policy_documents(iam, role_name), profile.read_only_patterns)
    role = iam.get_role(RoleName=role_name)["Role"]
    report.trust_problems = trust_problems(_doc(role.get("AssumeRolePolicyDocument") or {}),
                                           profile.external_id_required)
    return report


def render(report: Report) -> str:
    lines = [f"{report.role_arn}: {'read-only, OK' if report.ok else 'REFUSED'}"]
    for title, items in (
        ("write or out-of-scope actions allowed", report.allowed_writes),
        ("required read actions denied", report.denied_required),
        ("grants outside the read-only scope", report.extra_grants),
        ("trust policy", report.trust_problems),
        ("expected read actions denied (not fatal)", report.denied_expected),
        ("not checked", report.unchecked),
    ):
        if items:
            lines.append(f"  {title}:")
            lines.extend(f"    - {x}" for x in items)
    return "\n".join(lines)


def main(argv=None, iam=None) -> int:
    p = argparse.ArgumentParser(description="Check that a Dawnfix AWS role is read-only.")
    p.add_argument("role_arn")
    p.add_argument("--log-group", action="append", default=[], help="log group to check scoped reads against (repeat)")
    p.add_argument("--region", default="us-east-1", help="region of the log groups (default us-east-1)")
    p.add_argument("--profile", default="dawnfix", metavar="{" + ",".join(ROLE_PROFILES) + "}",
                   help="which role this is: dawnfix (error-log read role, default) or fleet "
                        "(the agency board's per-client read role)")
    p.add_argument("--aws-profile", help="AWS profile for the caller (not the role)")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    args = p.parse_args(argv)
    aws_profile = args.aws_profile
    if args.profile not in ROLE_PROFILES:
        # Before role profiles, --profile was the caller's AWS profile.
        print(f"verify_readonly: --profile {args.profile!r} is not a role profile; using it as --aws-profile "
              f"(role profiles: {', '.join(ROLE_PROFILES)})", file=sys.stderr)
        aws_profile = aws_profile or args.profile
        args.profile = "dawnfix"
    try:
        parse_role_arn(args.role_arn)
        if iam is None:
            import boto3
            iam = boto3.session.Session(profile_name=aws_profile).client("iam")
        report = verify(iam, args.role_arn, args.log_group, args.region, ROLE_PROFILES[args.profile])
    except UsageError as e:
        print(f"verify_readonly: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # botocore ClientError, NoCredentialsError, ...
        code = getattr(e, "response", {}).get("Error", {}).get("Code") if hasattr(e, "response") else None
        print(f"verify_readonly: AWS error: {code or type(e).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(report.as_dict(), indent=2) if args.json else render(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
