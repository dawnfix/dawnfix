"""Find references to SSM parameters and Secrets Manager secrets in ECS task
definitions and Lambda environments.

A plain env value is only ever reported when it *is* a name: an ARN, a known parameter
or secret name, or a path under a configured prefix. Any other value is dropped unseen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .model import Reference

ARN_RE = re.compile(
    r"arn:aws[a-z-]*:(?P<service>ssm|secretsmanager):(?P<region>[a-z0-9-]*):(?P<account>\d{12}):"
    r"(?P<resource>(?:parameter/[A-Za-z0-9_.\-/]+)|(?:secret:[A-Za-z0-9/_+=.@\-]+(?::[A-Za-z0-9_.\-]*){0,3}))"
)
SSM_NAME_RE = re.compile(r"^/?[A-Za-z0-9_.\-/]+$")
SECRET_NAME_RE = re.compile(r"^[A-Za-z0-9/_+=.@\-]+$")
SECRET_SUFFIX_RE = re.compile(r"-[A-Za-z0-9]{6}$")


@dataclass
class Known:
    """Names and prefixes collected across all environments being compared."""

    ssm_names: set[str] = field(default_factory=set)
    secret_names: set[str] = field(default_factory=set)
    ssm_prefixes: list[str] = field(default_factory=list)
    secret_prefixes: list[str] = field(default_factory=list)


def parse_arn(s: str):
    m = ARN_RE.fullmatch(s.strip())
    return m.groupdict() if m else None


def ssm_names_from_arn(resource: str) -> list[str]:
    """`parameter/a/b` is `/a/b`; `parameter/foo` may be `foo` or `/foo`."""
    rest = resource.split("/", 1)[1]
    return [f"/{rest}", rest] if "/" in rest else [rest, f"/{rest}"]


def secret_id_from_arn(resource: str) -> str:
    """`secret:name-AbCdEf:json-key:stage:id` -> `name-AbCdEf` (ECS allows the suffixes)."""
    return resource.split(":", 2)[1]


def secret_name_candidates(secret_id: str) -> list[str]:
    """A full ARN ends in -XXXXXX (random); a partial ARN does not."""
    out = [secret_id]
    if SECRET_SUFFIX_RE.search(secret_id):
        out.append(SECRET_SUFFIX_RE.sub("", secret_id))
    return out


def _ref_from_arn(env, source_kind, source, var, via, arn, default_region) -> Reference:
    p = parse_arn(arn)
    return Reference(env=env, source_kind=source_kind, source=source, var=var, via=via,
                     service=p["service"], target=arn.strip(), region=p["region"] or default_region,
                     account=p["account"])


def refs_from_value(env, source_kind, source, var, value, known: Known, region) -> list[Reference]:
    """References hidden in a plain env value. Returns [] for anything that is not a name."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        return []
    out = [_ref_from_arn(env, source_kind, source, var, "environment" if source_kind == "ecs" else "lambda.environment",
                         m.group(0), region)
           for m in ARN_RE.finditer(value)]
    if out:
        return out
    v = value.strip()
    via = "environment" if source_kind == "ecs" else "lambda.environment"

    def ref(service, target, prefix=False):
        return [Reference(env=env, source_kind=source_kind, source=source, var=var, via=via,
                          service=service, target=target, region=region, prefix=prefix)]

    if v.startswith("/") and SSM_NAME_RE.match(v):
        if v in known.ssm_names:
            return ref("ssm", v)
        base = v.rstrip("/") + "/"
        if any(n.startswith(base) for n in known.ssm_names):
            return ref("ssm", v, prefix=True)
        for p in known.ssm_prefixes:
            root = p.rstrip("/")
            if v == root or v.startswith(root + "/"):
                return ref("ssm", v, prefix=v.endswith("/") or v == root)
        return []
    if SECRET_NAME_RE.match(v):
        if v in known.secret_names:
            return ref("secretsmanager", v)
        for p in known.secret_prefixes:
            if len(p) >= 4 and v.startswith(p) and v != p:
                return ref("secretsmanager", v)
    return []


def refs_from_task_definition(env: str, source: str, td: dict, known: Known, region: str):
    """(plain env items, secret-ref items, references) for one task definition.

    Returns env entries as (container, var, kind, value_or_None); the caller hashes and
    drops values immediately.
    """
    entries, refs = [], []
    for c in td.get("containerDefinitions", []):
        cname = c.get("name", "?")
        for e in c.get("environment", []) or []:
            var = e.get("name", "")
            entries.append((cname, var, "plain", e.get("value")))
            refs += refs_from_value(env, "ecs", f"{source}/{cname}", var, e.get("value"), known, region)
        for s in c.get("secrets", []) or []:
            var, vf = s.get("name", ""), (s.get("valueFrom") or "").strip()
            entries.append((cname, var, "secret-ref", None))
            if not vf:
                continue
            if parse_arn(vf):
                refs.append(_ref_from_arn(env, "ecs", f"{source}/{cname}", var, "secrets.valueFrom", vf, region))
            else:  # ECS: a bare valueFrom is an SSM parameter name in the task's own account/region
                refs.append(Reference(env=env, source_kind="ecs", source=f"{source}/{cname}", var=var,
                                      via="secrets.valueFrom", service="ssm", target=vf, region=region))
        rc = (c.get("repositoryCredentials") or {}).get("credentialsParameter")
        if rc and parse_arn(rc):
            refs.append(_ref_from_arn(env, "ecs", f"{source}/{cname}", "(registry)", "repositoryCredentials",
                                      rc, region))
    return entries, refs


def refs_from_lambda(env: str, fn: dict, known: Known, region: str):
    name = fn.get("FunctionName", "?")
    variables = ((fn.get("Environment") or {}).get("Variables")) or {}
    entries, refs = [], []
    for var, value in variables.items():
        entries.append((var, value))
        refs += refs_from_value(env, "lambda", name, var, value, known, region)
    return entries, refs


# --- plaintext secrets in env vars --------------------------------------------------------
#
# A plain ECS `environment` entry or Lambda variable whose NAME says it is a credential
# (DB_PASSWORD, STRIPE_SECRET_KEY, apiToken) or whose VALUE has the shape of a well-known
# credential (sk_live_..., AKIA..., ghp_..., a PEM private key), holding a literal instead
# of a secrets.valueFrom / ARN / parameter name. Only the variable's name and the reason
# (an enum) are ever reported; the value is inspected here and dropped.

SECRET_NAME_TOKENS = (
    ("PASSWORD",), ("PASSWD",), ("PASSPHRASE",), ("SECRET",), ("TOKEN",), ("API", "KEY"), ("APIKEY",),
    ("PRIVATE", "KEY"), ("ACCESS", "KEY"), ("SECRET", "KEY"), ("SIGNING", "KEY"), ("ENCRYPTION", "KEY"),
    ("CLIENT", "SECRET"), ("AUTH", "KEY"), ("CREDENTIALS",), ("PWD",),
)
# Names that talk ABOUT a secret rather than hold one: SECRET_ARN, TOKEN_TTL, PASSWORD_MIN_LENGTH.
NOT_A_SECRET_SUFFIXES = {
    "ARN", "ARNS", "NAME", "ID", "IDS", "PATH", "PARAM", "PARAMETER", "PREFIX", "FILE", "DIR", "URL", "URI",
    "ENDPOINT", "HOST", "TTL", "EXPIRY", "EXPIRES", "EXPIRATION", "LIFETIME", "TIMEOUT", "LENGTH", "LEN",
    "SIZE", "HEADER", "TYPE", "ALGORITHM", "ALG", "ENABLED", "REQUIRED", "VERSION", "REGION", "ISSUER",
    "AUDIENCE", "SCOPE", "SCOPES", "POLICY", "ROTATION", "KMS", "MODE",
}
SECRET_VALUE_SHAPES = (
    re.compile(r"^(sk|rk)_live_[A-Za-z0-9]{10,}$"),            # Stripe live secret / restricted key
    re.compile(r"^AKIA[0-9A-Z]{16}$"),                          # AWS access key id
    re.compile(r"^(ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9]{30,}$"),    # GitHub tokens
    re.compile(r"^github_pat_[A-Za-z0-9_]{40,}$"),
    re.compile(r"^xox[abposr]-[A-Za-z0-9-]{10,}$"),            # Slack
    re.compile(r"^sk-(ant-|proj-)?[A-Za-z0-9_-]{20,}$"),        # Anthropic / OpenAI style
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
NOT_A_SECRET_VALUES = {"", "true", "false", "yes", "no", "on", "off", "none", "null", "nil", "-", "*", "redacted"}
PLACEHOLDER_RE = re.compile(r"^(\$\{[^}]*\}|\{\{[^}]*\}\}|<[^>]*>|%[A-Za-z_]+%)$")
URL_NO_USERINFO_RE = re.compile(r"^[a-z][a-z0-9+.-]*://[^/@\s]+(/\S*)?$", re.I)
ARN_ANY_RE = re.compile(r"^arn:aws[a-z-]*:")


def _name_tokens(var: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", var)
    return [t for t in re.split(r"[^A-Za-z0-9]+", spaced.upper()) if t]


def _name_says_secret(var: str) -> bool:
    toks = _name_tokens(var)
    if not toks or toks[-1] in NOT_A_SECRET_SUFFIXES:
        return False
    for pattern in SECRET_NAME_TOKENS:
        n = len(pattern)
        if any(tuple(toks[i:i + n]) == pattern for i in range(len(toks) - n + 1)):
            return True
    return False


def plaintext_secret_reason(var: str, value, refs: list) -> str | None:
    """'name' or 'value_shape' when a plain env var looks like a literal credential, else None.

    ``refs`` are the references already found in this value: a value that names a
    parameter/secret (or any ARN) is a reference, not a literal.
    """
    if refs or not isinstance(value, str):
        return None
    v = value.strip()
    if v.lower() in NOT_A_SECRET_VALUES or v.isdigit() or ARN_ANY_RE.match(v) or PLACEHOLDER_RE.match(v):
        return None
    if any(p.search(v) for p in SECRET_VALUE_SHAPES):
        return "value_shape"
    if not _name_says_secret(var):
        return None
    if v.startswith("/") or URL_NO_USERINFO_RE.match(v):
        return None   # a path or a URL without credentials in it
    return "name"
