"""Does a reference point at something that exists, and which environment owns it?"""
from __future__ import annotations

from dataclasses import dataclass

from .aws import AwsError, EnvAws, ReadOnlyViolation, error_code
from .config import EnvConf
from .model import Item, Reference, Snapshot
from .refs import parse_arn, secret_id_from_arn, secret_name_candidates, ssm_names_from_arn


def target_names(ref: Reference) -> list[str]:
    """Candidate store names for a reference target (an ARN expands to its name forms)."""
    p = parse_arn(ref.target)
    if not p:
        return secret_name_candidates(ref.target) if ref.service == "secretsmanager" else [ref.target]
    if p["service"] == "ssm":
        return ssm_names_from_arn(p["resource"])
    return secret_name_candidates(secret_id_from_arn(p["resource"]))


class Index:
    def __init__(self, snap: Snapshot):
        self.snap = snap
        self.ssm = {i.name: i for i in snap.by_kind("ssm")}
        self.secret = {i.name: i for i in snap.by_kind("secret")}

    def find(self, ref: Reference) -> list[Item]:
        names = target_names(ref)
        if ref.service == "ssm":
            if ref.prefix:
                base = ref.target.rstrip("/") + "/"
                return [i for n, i in self.ssm.items() if n.startswith(base)]
            return [self.ssm[n] for n in names if n in self.ssm][:1]
        return [self.secret[n] for n in names if n in self.secret][:1]


@dataclass
class Resolution:
    status: str               # ok | missing | unverifiable
    owner_env: str | None     # environment whose store holds the target
    items: list[Item]
    detail: str = ""


def matches_env(name: str, env: EnvConf) -> bool:
    for p in env.ssm_paths:
        root = p.rstrip("/")
        if p.startswith("/") and (name == root or name.startswith(root + "/")):
            return True
        if not p.startswith("/") and name.startswith(p):
            return True
    if any(name.startswith(p) for p in env.secret_prefixes):
        return True
    return any(m and m in name for m in env.markers)


class Resolver:
    """Resolves references against every snapshot, then by a targeted metadata lookup."""

    def __init__(self, snaps: dict[str, Snapshot], envs: dict[str, EnvConf], awss: dict[str, EnvAws] | None):
        self.snaps, self.envs, self.awss = snaps, envs, awss or {}
        self.index = {n: Index(s) for n, s in snaps.items()}
        self._cache: dict = {}

    def resolve(self, ref: Reference, lookup: bool = True) -> Resolution:
        own = self.snaps[ref.env]
        region = ref.region or own.region
        account = ref.account or own.account_id
        # search snapshots in the same account+region (own env first)
        order = [ref.env] + [n for n in self.snaps if n != ref.env]
        for n in order:
            s = self.snaps[n]
            if s.region != region:
                continue
            if account and s.account_id and s.account_id != account:
                continue
            hits = self.index[n].find(ref)
            if hits:
                return Resolution("ok", n, hits)
        if not lookup:
            return Resolution("unverifiable", None, [], "not looked up")
        # targeted lookup with the env whose account owns the target
        env_for_lookup = None
        if account is None or own.account_id in (None, account):
            env_for_lookup = ref.env
        else:
            for n, s in self.snaps.items():
                if s.account_id == account:
                    env_for_lookup = n
                    break
        if env_for_lookup is None or env_for_lookup not in self.awss:
            return Resolution("unverifiable", None, [], f"target in account {account} is not a configured environment")
        status, detail = self._lookup(env_for_lookup, ref, region)
        return Resolution(status, env_for_lookup if status == "ok" else None, [], detail)

    def _lookup(self, env_name: str, ref: Reference, region: str) -> tuple[str, str]:
        key = (env_name, ref.service, ref.target, ref.prefix, region)
        if key in self._cache:
            return self._cache[key]
        aws = self.awss[env_name]
        try:
            if ref.service == "ssm":
                c = aws.client("ssm", region)
                found = False
                names = [ref.target.rstrip("/") or "/"] if ref.prefix else target_names(ref)
                for n in names:
                    flt = ([{"Key": "Path", "Option": "Recursive", "Values": [n]}] if ref.prefix
                           else [{"Key": "Name", "Option": "Equals", "Values": [n]}])
                    if c.describe_parameters(ParameterFilters=flt, MaxResults=1 if ref.prefix else 10).get("Parameters"):
                        found = True
                        break
                out = ("ok", "") if found else ("missing", "no such parameter")
            else:
                c = aws.client("secretsmanager", region)
                p = parse_arn(ref.target)
                sid = ref.target if not p else ref.target.split(":secret:", 1)[0] + ":secret:" + secret_id_from_arn(p["resource"])
                try:
                    d = c.describe_secret(SecretId=sid)
                    out = ("missing", "secret is scheduled for deletion") if d.get("DeletedDate") else ("ok", "")
                except Exception as e:
                    code = error_code(e)
                    if code == "ResourceNotFoundException":
                        out = ("missing", "no such secret")
                    else:
                        raise
        except ReadOnlyViolation:
            raise
        except AwsError as e:
            out = ("unverifiable", e.code)
        except Exception as e:
            out = ("unverifiable", error_code(e))
        self._cache[key] = out
        return out

    def cross_env(self, ref: Reference, owner_env: str | None) -> str | None:
        """Name of the other environment this reference belongs to, if any."""
        own_conf = self.envs[ref.env]
        own_acct = self.snaps[ref.env].account_id
        if ref.account and own_acct and ref.account != own_acct:
            for n, s in self.snaps.items():
                if n != ref.env and s.account_id == ref.account:
                    return n
        names = target_names(ref)
        if any(matches_env(x, own_conf) for x in names):
            return None
        for n, conf in self.envs.items():
            if n != ref.env and any(matches_env(x, conf) for x in names):
                return n
        if owner_env and owner_env != ref.env:
            return owner_env
        return None
