"""What collection produces. Nothing here ever holds a config value, only names,
metadata and (with --compare-hashes) an in-memory salted digest that is never serialised."""
from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass, field


class ValueHasher:
    """Salted SHA-256 (HMAC) with a fresh random salt per run.

    The salt lives only in this object, so a digest is useless outside the process: it
    can say "dev and prod hold the same value", never what the value is.
    """

    def __init__(self, salt: bytes | None = None):
        self._salt = salt or os.urandom(32)

    def digest(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            value = value.encode("utf-8")
        return hmac.new(self._salt, value, hashlib.sha256).hexdigest()

    def __repr__(self) -> str:
        return "ValueHasher(<salt hidden>)"


@dataclass
class Item:
    env: str
    kind: str            # ssm | secret | ecs | lambda
    name: str            # full name: /app/dev/DB_URL, app/dev/db, api/app/DB_URL, fn/DB_URL
    key: str             # normalised name used for comparison
    type: str            # SSM: String|StringList|SecureString; secret: Secret; ecs/lambda: plain|secret-ref
    arn: str | None = None
    meta: dict = field(default_factory=dict)
    digest: str | None = field(default=None, repr=False)   # never serialised

    @property
    def ckey(self) -> str:
        return f"{self.kind}:{self.key}"

    @property
    def is_secret(self) -> bool:
        return self.type in ("SecureString", "Secret")

    def to_dict(self) -> dict:
        return {"env": self.env, "kind": self.kind, "name": self.name, "key": self.ckey,
                "type": self.type, "arn": self.arn, "meta": _jsonable(self.meta)}


@dataclass
class Reference:
    env: str
    source_kind: str      # ecs | lambda
    source: str           # "cluster/service (family:rev)" or function name
    var: str              # env var / secret name inside the container or function
    via: str              # secrets.valueFrom | environment | repositoryCredentials | lambda.environment
    service: str          # ssm | secretsmanager
    target: str           # name, ARN or path prefix (never a raw value unless it IS the name)
    region: str | None = None
    account: str | None = None
    prefix: bool = False  # a path prefix (CONFIG_PATH=/app/prod/) referencing a whole subtree

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in
                ("env", "source_kind", "source", "var", "via", "service", "target", "region", "account", "prefix")}


@dataclass
class Snapshot:
    env: str
    region: str
    account_id: str | None
    items: list[Item] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    hashed: bool = False

    def by_kind(self, *kinds) -> list[Item]:
        return [i for i in self.items if i.kind in kinds]


def _jsonable(v):
    from datetime import datetime

    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, datetime):
        return v.isoformat()
    return v
