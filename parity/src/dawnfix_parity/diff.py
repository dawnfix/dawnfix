"""Compare two snapshots by normalised key. Names and metadata only; with
--compare-hashes, digests are compared here and reduced to equal/differs."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field

from .config import Config
from .model import Item, Snapshot
from .resolve import Resolver

FINDING_KINDS = {
    # kind: (default severity, fails `parity check` by default)
    "missing_in_left": ("medium", True),
    "missing_in_right": ("medium", True),
    "type_mismatch": ("high", True),
    "dangling_reference": ("high", True),
    "cross_env_reference": ("high", True),
    "value_shared": ("high", True),
    "value_differs": ("medium", True),
    "unverifiable_reference": ("info", False),
    "duplicate_key": ("low", False),
    "plaintext_secret": ("high", True),
}
DEFAULT_FAIL_ON = tuple(k for k, (_, fails) in FINDING_KINDS.items() if fails)
SECRETISH = ("SecureString", "Secret", "secret-ref")


@dataclass
class Finding:
    kind: str
    key: str
    message: str
    severity: str = ""
    env: str | None = None
    details: dict = field(default_factory=dict)
    allowed: bool = False
    allow_reason: str = ""

    def __post_init__(self):
        if not self.severity:
            self.severity = FINDING_KINDS[self.kind][0]

    def to_dict(self) -> dict:
        return {"kind": self.kind, "severity": self.severity, "key": self.key, "env": self.env,
                "message": self.message, "details": self.details, "allowed": self.allowed,
                "allow_reason": self.allow_reason}


@dataclass
class DiffResult:
    left: str
    right: str
    findings: list[Finding]
    counts: dict
    hashed: bool
    warnings: list[str]

    def active(self, fail_on=DEFAULT_FAIL_ON) -> list[Finding]:
        return [f for f in self.findings if not f.allowed and f.kind in fail_on]

    def to_dict(self) -> dict:
        return {"left": self.left, "right": self.right, "hashed": self.hashed, "counts": self.counts,
                "warnings": self.warnings, "findings": [f.to_dict() for f in self.findings]}


def _source_key(it: Item) -> str | None:
    if it.kind in ("ecs", "lambda"):
        return f"{it.kind}:{it.key.split('/', 1)[0]}"
    return None


def _group(items: list[Item]):
    out: dict[str, list[Item]] = {}
    for i in items:
        out.setdefault(i.ckey, []).append(i)
    return out


def _desc(it: Item) -> dict:
    return {"name": it.name, "type": it.type, **({"arn": it.arn} if it.arn else {})}


def diff(cfg: Config, left: Snapshot, right: Snapshot, resolver: Resolver) -> DiffResult:
    L, R = left.env, right.env
    findings: list[Finding] = []
    lg, rg = _group(left.items), _group(right.items)

    for env, groups in ((L, lg), (R, rg)):
        for k, its in groups.items():
            if len({i.name for i in its}) > 1:
                findings.append(Finding("duplicate_key", k, f"{len(its)} names in {env} normalise to {k}", env=env,
                                        details={"names": sorted({i.name for i in its})}))

    l_sources = {_source_key(i) for i in left.items} - {None}
    r_sources = {_source_key(i) for i in right.items} - {None}
    reported_sources = set()
    for k in sorted(set(lg) | set(rg)):
        li, ri = lg.get(k, []), rg.get(k, [])
        if li and ri:
            lt, rt = sorted({i.type for i in li}), sorted({i.type for i in ri})
            if lt != rt:
                sev = "high" if (any(t in SECRETISH for t in lt) != any(t in SECRETISH for t in rt)) else "medium"
                findings.append(Finding("type_mismatch", k, f"{'/'.join(lt)} in {L}, {'/'.join(rt)} in {R}",
                                        severity=sev, details={L: _desc(li[0]), R: _desc(ri[0])}))
            continue
        present, missing_env, kind = (li, R, "missing_in_right") if li else (ri, L, "missing_in_left")
        other_sources = r_sources if li else l_sources
        sk = _source_key(present[0])
        if sk is not None and sk not in other_sources:
            if (kind, sk) in reported_sources:
                continue
            reported_sources.add((kind, sk))
            what = "service" if present[0].kind == "ecs" else "function"
            findings.append(Finding(kind, sk + "/*", f"whole {what} missing in {missing_env}",
                                    env=missing_env, details={"example": _desc(present[0])}))
            continue
        findings.append(Finding(kind, k, f"missing in {missing_env}", env=missing_env,
                                details={"present": _desc(present[0])}))

    hashed = left.hashed and right.hashed
    equal = differ = 0
    if hashed:
        for k in sorted(set(lg) & set(rg)):
            ld, rd = lg[k][0].digest, rg[k][0].digest
            if not ld or not rd:
                continue
            if ld == rd:
                equal += 1
                secretish = lg[k][0].is_secret or rg[k][0].is_secret or _glob(k, cfg.must_differ)
                if secretish:
                    findings.append(Finding("value_shared", k, f"same value in {L} and {R}"))
            else:
                differ += 1
                if _glob(k, cfg.must_match):
                    findings.append(Finding("value_differs", k, f"value differs between {L} and {R}"))

    for snap in (left, right):
        for ref in snap.references:
            res = resolver.resolve(ref)
            rk = f"ref:{ref.source_kind}:{ref.source}/{ref.var}"
            det = {"source": ref.source, "var": ref.var, "via": ref.via, "target": ref.target,
                   "service": ref.service}
            if res.status == "missing":
                findings.append(Finding("dangling_reference", rk,
                                        f"{ref.var} in {snap.env} references {ref.service} {ref.target}, which does not exist",
                                        env=snap.env, details={**det, "detail": res.detail}))
            elif res.status == "unverifiable":
                findings.append(Finding("unverifiable_reference", rk,
                                        f"could not check {ref.target} ({res.detail})", env=snap.env, details=det))
            other = resolver.cross_env(ref, res.owner_env)
            if other:
                findings.append(Finding("cross_env_reference", rk,
                                        f"{ref.var} in {snap.env} references {other}'s {ref.target}",
                                        env=snap.env, details={**det, "other_env": other}))

    for snap in (left, right):
        for it in snap.items:
            reason = it.meta.get("plaintext_secret")
            if reason:
                why = ("its name says it is a credential" if reason == "name"
                       else "it has the shape of a known credential")
                findings.append(Finding(
                    "plaintext_secret", it.ckey,
                    f"{it.name.rsplit('/', 1)[-1]} in {snap.env} holds a literal value and {why}: move it to "
                    "Secrets Manager or an SSM SecureString and reference it (secrets.valueFrom / ARN)",
                    env=snap.env, details={"name": it.name, "reason": reason}))

    for f in findings:
        for a in cfg.allow:
            if (a.kind in ("*", f.kind)) and fnmatch.fnmatchcase(f.key, a.key):
                f.allowed, f.allow_reason = True, a.reason
                break

    counts = {"keys_left": len(lg), "keys_right": len(rg), "references": len(left.references) + len(right.references)}
    if hashed:
        counts.update(values_equal=equal, values_differ=differ)
    for f in findings:
        counts[f.kind] = counts.get(f.kind, 0) + 1
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    findings.sort(key=lambda f: (f.allowed, order.get(f.severity, 9), f.kind, f.key))
    return DiffResult(L, R, findings, counts, hashed, left.warnings + right.warnings)


def _glob(key: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(key, p) for p in patterns)
