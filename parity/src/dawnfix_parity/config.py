"""`.parity.yml`: environments, normalisation rules, allow-list, inventory thresholds."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

KINDS = ("ssm", "secret", "ecs", "lambda")


class ConfigError(ValueError):
    pass


@dataclass
class Rule:
    """One normalisation step applied to a name before keys are compared."""

    op: str            # strip_prefix | replace | regex | env_token
    arg: str
    to: str = ""
    kinds: tuple[str, ...] = KINDS

    def apply(self, kind: str, name: str) -> str:
        if kind not in self.kinds:
            return name
        if self.op == "strip_prefix":
            return name[len(self.arg):] if name.startswith(self.arg) else name
        if self.op == "replace":
            return name.replace(self.arg, self.to)
        if self.op == "regex":
            return re.sub(self.arg, self.to, name)
        if self.op == "env_token":
            # `dev` as a whole token between separators: api-dev, /dev/, dev_db -> {env}
            return re.sub(rf"(?<![A-Za-z0-9]){re.escape(self.arg)}(?![A-Za-z0-9])", "{env}", name)
        raise ConfigError(f"unknown normalise op {self.op}")


@dataclass
class EcsConf:
    cluster: str
    services: list[str] = field(default_factory=lambda: ["*"])   # names or globs
    task_definitions: list[str] = field(default_factory=list)    # families (latest ACTIVE)


@dataclass
class EnvConf:
    name: str
    region: str
    profile: str | None = None
    role_arn: str | None = None
    account_id: str | None = None
    ssm_paths: list[str] = field(default_factory=list)
    secret_prefixes: list[str] = field(default_factory=list)
    ecs: list[EcsConf] = field(default_factory=list)
    lambda_patterns: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    strip_matched_prefix: bool = True
    markers: list[str] = field(default_factory=list)   # extra strings that mean "this env"

    def own_markers(self) -> list[str]:
        """Strings that identify this environment inside a name or ARN."""
        out = [p.rstrip("/") + "/" if p.startswith("/") else p for p in self.ssm_paths]
        out += list(self.secret_prefixes) + list(self.markers)
        return [m for m in out if m]

    def normalise(self, kind: str, name: str, matched_prefix: str | None = None) -> str:
        if matched_prefix and self.strip_matched_prefix and name.startswith(matched_prefix):
            name = name[len(matched_prefix):].lstrip("/") or name
        for r in self.rules:
            name = r.apply(kind, name)
        return name


@dataclass
class AllowEntry:
    kind: str          # finding kind or "*"
    key: str           # glob over the normalised key, e.g. "ssm:DEBUG_*"
    reason: str = ""


@dataclass
class Config:
    envs: dict[str, EnvConf]
    allow: list[AllowEntry] = field(default_factory=list)
    unread_days: int = 90
    rotation_max_age_days: int = 90
    must_match: list[str] = field(default_factory=list)    # keys whose values must be equal (hash mode)
    must_differ: list[str] = field(default_factory=list)   # extra keys that must differ (secrets always do)

    def env(self, name: str) -> EnvConf:
        if name not in self.envs:
            raise ConfigError(f"unknown environment {name!r}; defined: {', '.join(sorted(self.envs))}")
        return self.envs[name]


def _list(v, what) -> list:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    if not isinstance(v, list):
        raise ConfigError(f"{what} must be a list")
    return v


def _rule(raw, where) -> Rule:
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: each normalise rule is a mapping")
    kinds = tuple(_list(raw.get("kinds"), f"{where}.kinds")) or KINDS
    bad = set(kinds) - set(KINDS)
    if bad:
        raise ConfigError(f"{where}: unknown kinds {sorted(bad)}")
    if "strip_prefix" in raw:
        return Rule("strip_prefix", str(raw["strip_prefix"]), kinds=kinds)
    if "env_token" in raw:
        return Rule("env_token", str(raw["env_token"]), kinds=kinds)
    if "replace" in raw:
        r = raw["replace"]
        if not isinstance(r, dict) or "from" not in r:
            raise ConfigError(f"{where}: replace needs {{from, to}}")
        return Rule("replace", str(r["from"]), str(r.get("to", "")), kinds)
    if "regex" in raw:
        r = raw["regex"]
        if not isinstance(r, dict) or "pattern" not in r:
            raise ConfigError(f"{where}: regex needs {{pattern, to}}")
        try:
            re.compile(r["pattern"])
        except re.error as e:
            raise ConfigError(f"{where}: bad regex: {e}") from None
        return Rule("regex", str(r["pattern"]), str(r.get("to", "")), kinds)
    raise ConfigError(f"{where}: rule needs one of strip_prefix, replace, regex, env_token")


def _env(name: str, raw: dict) -> EnvConf:
    if not isinstance(raw, dict):
        raise ConfigError(f"environments.{name} must be a mapping")
    if not raw.get("region"):
        raise ConfigError(f"environments.{name}.region is required")
    aws = raw.get("aws") or {}
    ssm = raw.get("ssm") or {}
    sec = raw.get("secrets") or {}
    lam = raw.get("lambda") or {}
    ecs_raw = raw.get("ecs") or []
    if isinstance(ecs_raw, dict):
        ecs_raw = [ecs_raw]
    ecs = []
    for i, e in enumerate(ecs_raw):
        if not isinstance(e, dict) or not e.get("cluster"):
            raise ConfigError(f"environments.{name}.ecs[{i}].cluster is required")
        ecs.append(EcsConf(
            cluster=str(e["cluster"]),
            services=[str(s) for s in _list(e.get("services", ["*"]), "ecs.services")],
            task_definitions=[str(s) for s in _list(e.get("task_definitions"), "ecs.task_definitions")],
        ))
    rules = [_rule(r, f"environments.{name}.normalize[{i}]")
             for i, r in enumerate(_list(raw.get("normalize"), "normalize"))]
    acct = aws.get("account_id", raw.get("account_id"))
    if acct is not None and not re.fullmatch(r"\d{12}", str(acct)):
        raise ConfigError(f"environments.{name}.account_id must be 12 digits")
    return EnvConf(
        name=name,
        region=str(raw["region"]),
        profile=aws.get("profile", raw.get("profile")),
        role_arn=aws.get("role_arn", raw.get("role_arn")),
        account_id=str(acct) if acct is not None else None,
        ssm_paths=[str(p) for p in _list(ssm.get("paths"), "ssm.paths")],
        secret_prefixes=[str(p) for p in _list(sec.get("prefixes"), "secrets.prefixes")],
        ecs=ecs,
        lambda_patterns=[str(p) for p in _list(lam.get("functions"), "lambda.functions")],
        rules=rules,
        strip_matched_prefix=bool(raw.get("strip_matched_prefix", True)),
        markers=[str(m) for m in _list(raw.get("markers"), "markers")],
    )


def parse(doc) -> Config:
    if not isinstance(doc, dict):
        raise ConfigError("config must be a mapping")
    if doc.get("version", 1) != 1:
        raise ConfigError("unsupported config version (expected 1)")
    envs_raw = doc.get("environments")
    if not isinstance(envs_raw, dict) or not envs_raw:
        raise ConfigError("environments: at least one environment is required")
    envs = {str(k): _env(str(k), v) for k, v in envs_raw.items()}
    allow = []
    for i, a in enumerate(_list(doc.get("allow"), "allow")):
        if not isinstance(a, dict) or "key" not in a:
            raise ConfigError(f"allow[{i}] needs key")
        allow.append(AllowEntry(kind=str(a.get("kind", "*")), key=str(a["key"]), reason=str(a.get("reason", ""))))
    inv = doc.get("inventory") or {}
    hashes = doc.get("hashes") or {}
    try:
        unread = int(inv.get("unread_days", 90))
        rot = int(inv.get("rotation_max_age_days", 90))
    except (TypeError, ValueError):
        raise ConfigError("inventory thresholds must be integers") from None
    return Config(
        envs=envs, allow=allow, unread_days=unread, rotation_max_age_days=rot,
        must_match=[str(x) for x in _list(hashes.get("must_match"), "hashes.must_match")],
        must_differ=[str(x) for x in _list(hashes.get("must_differ"), "hashes.must_differ")],
    )


def load(path: str | Path) -> Config:
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"config not found: {p}")
    try:
        return parse(yaml.safe_load(p.read_text()))
    except yaml.YAMLError as e:
        raise ConfigError(f"{p}: invalid YAML: {e}") from None
