"""fleet.yml: which accounts belong to which client, and how to reach them read-only.

    version: 1
    clients:
      k3m9x2a7b4cd:                      # the client workspace slug (POST /v1/clients)
        accounts:
          - provider: aws
            env: prod
            account_id: "123456789012"
            role_arn: arn:aws:iam::123456789012:role/fleet-read   # omit in the client's own CI
            external_id_env: FLEET_EXTERNAL_ID_K3M9              # env var holding the External ID
            regions: [us-east-1, eu-west-1]
            checks: [alarms, spend, certs]                       # default: all three

Clients are keyed by their board slug, which is random, so the file names nobody. Every
object is closed: an unknown key is an error, not something quietly ignored.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

SLUG = re.compile(r"^[a-z0-9]{1,40}$")
ACCOUNT_ID = re.compile(r"^\d{12}$")
ROLE_ARN = re.compile(r"^arn:(aws[a-z-]*):iam::(\d{12}):role/(?:[\w+=,.@-]+/)*[\w+=,.@-]{1,64}$")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
REGION = re.compile(r"^[a-z]{2}(-[a-z]+)+-\d$")

ENVS = ("prod", "staging", "dev", "shared", "other")
CHECKS = ("alarms", "spend", "certs")
MAX_ACCOUNTS = 50
MAX_REGIONS = 20


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Account:
    provider: str
    env: str
    account_id: str
    regions: tuple[str, ...]
    checks: frozenset[str]
    role_arn: str | None = None
    external_id_env: str | None = None

    @property
    def assume(self) -> bool:
        return self.role_arn is not None


@dataclass(frozen=True)
class Client:
    slug: str
    accounts: tuple[Account, ...] = field(default_factory=tuple)


def _closed(obj, path: str, allowed: set[str], required: set[str]) -> dict:
    if not isinstance(obj, dict):
        raise ConfigError(f"{path}: expected a mapping")
    for key in obj:
        if key not in allowed:
            raise ConfigError(f"{path}: unknown key {key!r}")
    for key in required:
        if key not in obj:
            raise ConfigError(f"{path}: missing {key!r}")
    return obj


def _account(raw, path: str) -> Account:
    a = _closed(raw, path, {"provider", "env", "account_id", "role_arn", "external_id_env", "regions", "checks"},
                {"provider", "env", "account_id", "regions"})
    provider = a["provider"]
    if provider == "gcp":
        raise ConfigError(f"{path}/provider: gcp is not implemented yet (the schema reserves it)")
    if provider != "aws":
        raise ConfigError(f"{path}/provider: must be aws")
    if a["env"] not in ENVS:
        raise ConfigError(f"{path}/env: one of {', '.join(ENVS)}")
    account_id = str(a["account_id"])
    if not ACCOUNT_ID.match(account_id):
        raise ConfigError(f"{path}/account_id: twelve digits, quoted")

    role_arn = a.get("role_arn")
    external_id_env = a.get("external_id_env")
    if role_arn is not None:
        m = ROLE_ARN.match(str(role_arn))
        if not m:
            raise ConfigError(f"{path}/role_arn: not an IAM role ARN")
        if m.group(2) != account_id:
            raise ConfigError(f"{path}/role_arn: account differs from account_id")
        # A role a third party assumes without an External ID is a confused-deputy hole.
        if external_id_env is None:
            raise ConfigError(f"{path}/external_id_env: required with role_arn")
    if external_id_env is not None:
        if role_arn is None:
            raise ConfigError(f"{path}/external_id_env: only meaningful with role_arn")
        if not ENV_NAME.match(str(external_id_env)):
            raise ConfigError(f"{path}/external_id_env: an environment variable name")

    regions = a["regions"]
    if not isinstance(regions, list) or not 1 <= len(regions) <= MAX_REGIONS:
        raise ConfigError(f"{path}/regions: a list of 1 to {MAX_REGIONS} regions")
    for i, r in enumerate(regions):
        if not isinstance(r, str) or not REGION.match(r):
            raise ConfigError(f"{path}/regions/{i}: not a region name")
    if len(set(regions)) != len(regions):
        raise ConfigError(f"{path}/regions: duplicates")

    checks = a.get("checks", list(CHECKS))
    if not isinstance(checks, list) or not checks:
        raise ConfigError(f"{path}/checks: a non-empty list")
    for c in checks:
        if c not in CHECKS:
            raise ConfigError(f"{path}/checks: one of {', '.join(CHECKS)}")

    return Account(provider=provider, env=a["env"], account_id=account_id, regions=tuple(regions),
                   checks=frozenset(checks), role_arn=role_arn, external_id_env=external_id_env)


def parse(doc) -> dict[str, Client]:
    top = _closed(doc, "", {"version", "clients"}, {"version", "clients"})
    if top["version"] != 1:
        raise ConfigError("/version: must be 1")
    clients_raw = top["clients"]
    if not isinstance(clients_raw, dict) or not clients_raw:
        raise ConfigError("/clients: a non-empty mapping of client slug to accounts")
    out: dict[str, Client] = {}
    for slug, raw in clients_raw.items():
        path = f"/clients/{slug}"
        if not isinstance(slug, str) or not SLUG.match(slug):
            raise ConfigError(f"{path}: client keys are board slugs (lowercase letters and digits)")
        c = _closed(raw, path, {"accounts"}, {"accounts"})
        accounts = c["accounts"]
        if not isinstance(accounts, list) or not 1 <= len(accounts) <= MAX_ACCOUNTS:
            raise ConfigError(f"{path}/accounts: 1 to {MAX_ACCOUNTS} accounts")
        parsed = tuple(_account(a, f"{path}/accounts/{i}") for i, a in enumerate(accounts))
        ids = [(a.provider, a.account_id) for a in parsed]
        if len(set(ids)) != len(ids):
            raise ConfigError(f"{path}/accounts: the same account twice")
        out[slug] = Client(slug=slug, accounts=parsed)
    return out


def load(path: str) -> dict[str, Client]:
    try:
        with open(path) as f:
            doc = yaml.safe_load(f)
    except OSError as e:
        raise ConfigError(f"cannot read {path}: {e.strerror}") from None
    except yaml.YAMLError:
        raise ConfigError(f"{path}: not valid YAML") from None
    return parse(doc)
