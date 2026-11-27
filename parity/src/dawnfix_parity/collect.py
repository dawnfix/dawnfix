"""Read one environment: SSM, Secrets Manager, ECS task definitions, Lambda env.

Two phases, because a plain env value can only be recognised as a reference once the
names in every environment are known:

    stores = [collect_stores(env) for env in envs]     # SSM + Secrets Manager
    known = known_names(stores, envs)
    collect_compute(snapshot, env, known)              # ECS + Lambda, references

Values are fetched only with a hasher (--compare-hashes) and are turned into a salted
digest on the line they arrive; the plaintext never leaves the local scope.
"""
from __future__ import annotations

import fnmatch

from .aws import AwsError, EnvAws, ReadOnlyViolation, error_code
from .config import EnvConf
from .model import Item, Snapshot, ValueHasher
from .refs import Known, parse_arn, plaintext_secret_reason, refs_from_lambda, refs_from_task_definition

MAX_PAGES = 200


def _call(where, fn, **kw):
    try:
        return fn(**kw)
    except ReadOnlyViolation:
        raise
    except Exception as e:
        raise AwsError(error_code(e), where) from None


def _ssm_filters(path: str) -> list[dict]:
    if path.startswith("/"):
        root = path.rstrip("/") or "/"
        return [{"Key": "Path", "Option": "Recursive", "Values": [root]}]
    return [{"Key": "Name", "Option": "BeginsWith", "Values": [path]}]


def _matched_prefix(name: str, prefixes: list[str]) -> str | None:
    best = None
    for p in prefixes:
        cand = (p.rstrip("/") + "/") if p.startswith("/") else p
        if name.startswith(cand) and (best is None or len(cand) > len(best)):
            best = cand
    return best


def collect_stores(env: EnvConf, aws: EnvAws, hasher: ValueHasher | None = None) -> Snapshot:
    snap = Snapshot(env=env.name, region=env.region, account_id=env.account_id, hashed=hasher is not None)
    ssm = aws.client("ssm") if env.ssm_paths else None
    seen = set()
    for path in env.ssm_paths:
        params = {"ParameterFilters": _ssm_filters(path), "MaxResults": 50}
        for _ in range(MAX_PAGES):
            resp = _call("ssm:DescribeParameters", ssm.describe_parameters, **params)
            for p in resp.get("Parameters", []):
                name = p["Name"]
                if name in seen:
                    continue
                seen.add(name)
                mp = _matched_prefix(name, env.ssm_paths)
                snap.items.append(Item(
                    env=env.name, kind="ssm", name=name, key=env.normalise("ssm", name, mp),
                    type=p.get("Type", "String"), arn=p.get("ARN"),
                    meta={"version": p.get("Version"), "last_changed": p.get("LastModifiedDate"),
                          "last_changed_by": p.get("LastModifiedUser"), "tier": p.get("Tier"),
                          "kms_key": p.get("KeyId")},
                ))
            token = resp.get("NextToken")
            if not token:
                break
            params["NextToken"] = token
        else:
            snap.warnings.append(f"ssm {path}: stopped after {MAX_PAGES} pages")

    if env.secret_prefixes:
        sm = aws.client("secretsmanager")
        for prefix in env.secret_prefixes:
            params = {"Filters": [{"Key": "name", "Values": [prefix]}], "MaxResults": 100}
            for _ in range(MAX_PAGES):
                resp = _call("secretsmanager:ListSecrets", sm.list_secrets, **params)
                for s in resp.get("SecretList", []):
                    name = s["Name"]
                    # the API filter is a case-insensitive prefix match; be exact here
                    if not name.startswith(prefix) or ("sm", name) in seen:
                        continue
                    seen.add(("sm", name))
                    snap.items.append(Item(
                        env=env.name, kind="secret", name=name,
                        key=env.normalise("secret", name, _matched_prefix(name, env.secret_prefixes)),
                        type="Secret", arn=s.get("ARN"),
                        meta={"last_changed": s.get("LastChangedDate"), "last_accessed": s.get("LastAccessedDate"),
                              "created": s.get("CreatedDate"), "rotation_enabled": bool(s.get("RotationEnabled")),
                              "last_rotated": s.get("LastRotatedDate"), "next_rotation": s.get("NextRotationDate"),
                              "kms_key": s.get("KmsKeyId"), "owning_service": s.get("OwningService")},
                    ))
                token = resp.get("NextToken")
                if not token:
                    break
                params["NextToken"] = token

    if snap.account_id is None:
        for it in snap.items:
            p = parse_arn(it.arn or "")
            if p:
                snap.account_id = p["account"]
                break

    if hasher is not None:
        _hash_store_values(snap, aws, hasher)
    return snap


def _hash_store_values(snap: Snapshot, aws: EnvAws, hasher: ValueHasher) -> None:
    ssm_items = {i.name: i for i in snap.by_kind("ssm")}
    names = list(ssm_items)
    if names:
        ssm = aws.client("ssm")
        for start in range(0, len(names), 10):
            resp = _call("ssm:GetParameters", ssm.get_parameters, Names=names[start:start + 10], WithDecryption=True)
            for p in resp.get("Parameters", []):
                ssm_items[p["Name"]].digest = hasher.digest(p.get("Value"))
            del resp
    secrets = snap.by_kind("secret")
    if secrets:
        sm = aws.client("secretsmanager")
        for it in secrets:
            try:
                resp = sm.get_secret_value(SecretId=it.arn or it.name)
            except ReadOnlyViolation:
                raise
            except Exception as e:
                snap.warnings.append(f"secret {it.name}: value not hashed ({error_code(e)})")
                continue
            it.digest = hasher.digest(resp.get("SecretString") if "SecretString" in resp else resp.get("SecretBinary"))
            del resp


def known_names(snaps: list[Snapshot], envs: list[EnvConf]) -> Known:
    k = Known()
    for s in snaps:
        k.ssm_names |= {i.name for i in s.by_kind("ssm")}
        k.secret_names |= {i.name for i in s.by_kind("secret")}
    for e in envs:
        k.ssm_prefixes += [p for p in e.ssm_paths if p.startswith("/")]
        k.secret_prefixes += list(e.secret_prefixes)
    return k


def _glob_any(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def collect_compute(snap: Snapshot, env: EnvConf, aws: EnvAws, known: Known,
                    hasher: ValueHasher | None = None) -> Snapshot:
    for ecs_conf in env.ecs:
        ecs = aws.client("ecs")
        targets = []   # (label, taskDefinition arn-or-family)
        if ecs_conf.services:
            arns, params = [], {"cluster": ecs_conf.cluster, "maxResults": 100}
            for _ in range(MAX_PAGES):
                resp = _call("ecs:ListServices", ecs.list_services, **params)
                arns += resp.get("serviceArns", [])
                if not resp.get("nextToken"):
                    break
                params["nextToken"] = resp["nextToken"]
            for start in range(0, len(arns), 10):
                resp = _call("ecs:DescribeServices", ecs.describe_services,
                             cluster=ecs_conf.cluster, services=arns[start:start + 10])
                for svc in resp.get("services", []):
                    if _glob_any(svc["serviceName"], ecs_conf.services) and svc.get("taskDefinition"):
                        targets.append((svc["serviceName"], svc["taskDefinition"]))
        targets += [(fam, fam) for fam in ecs_conf.task_definitions]
        for label, td_id in targets:
            td = _call("ecs:DescribeTaskDefinition", ecs.describe_task_definition,
                       taskDefinition=td_id)["taskDefinition"]
            source = f"{ecs_conf.cluster}/{label} ({td.get('family')}:{td.get('revision')})"
            entries, refs = refs_from_task_definition(env.name, source, td, known, env.region)
            del td
            snap.references += refs
            for container, var, typ, value in entries:
                raw = f"{label}/{container}/{var}"
                meta = {"source": source}
                if typ == "plain":
                    own = [r for r in refs if r.var == var and r.via == "environment"
                           and r.source.endswith(f"/{container}")]
                    reason = plaintext_secret_reason(var, value, own)
                    if reason:
                        meta["plaintext_secret"] = reason
                snap.items.append(Item(
                    env=env.name, kind="ecs", name=raw, key=env.normalise("ecs", raw), type=typ,
                    meta=meta,
                    digest=hasher.digest(value) if (hasher and typ == "plain") else None,
                ))
            del entries

    if env.lambda_patterns:
        lam = aws.client("lambda")
        params = {"MaxItems": 50}
        for _ in range(MAX_PAGES):
            resp = _call("lambda:ListFunctions", lam.list_functions, **params)
            for fn in resp.get("Functions", []):
                name = fn.get("FunctionName", "")
                if not _glob_any(name, env.lambda_patterns):
                    continue
                entries, refs = refs_from_lambda(env.name, fn, known, env.region)
                snap.references += refs
                for var, value in entries:
                    raw = f"{name}/{var}"
                    meta = {"source": name, "last_changed": fn.get("LastModified")}
                    reason = plaintext_secret_reason(var, value, [r for r in refs if r.var == var])
                    if reason:
                        meta["plaintext_secret"] = reason
                    snap.items.append(Item(
                        env=env.name, kind="lambda", name=raw, key=env.normalise("lambda", raw), type="plain",
                        meta=meta,
                        digest=hasher.digest(value) if hasher else None,
                    ))
                del entries
            marker = resp.get("NextMarker")
            if not marker:
                break
            params["Marker"] = marker
    return snap


def collect(envs: list[EnvConf], awss: dict[str, EnvAws], hasher: ValueHasher | None = None) -> dict[str, Snapshot]:
    snaps = {e.name: collect_stores(e, awss[e.name], hasher) for e in envs}
    known = known_names(list(snaps.values()), envs)
    for e in envs:
        collect_compute(snaps[e.name], e, awss[e.name], known, hasher)
    return snaps
