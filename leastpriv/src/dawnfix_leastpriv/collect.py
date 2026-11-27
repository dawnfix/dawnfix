"""Read a role, its policies and the evidence of what it actually used. Read-only."""
from __future__ import annotations

import json
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime

from botocore.exceptions import BotoCoreError, ClientError

from .guard import ReadOnlyViolation

MAX_PAGES = 100


@dataclass
class Policy:
    name: str
    kind: str  # inline | customer_managed | aws_managed
    document: dict
    arn: str | None = None
    version_id: str | None = None


@dataclass
class ServiceUsage:
    namespace: str
    name: str
    last: datetime | None
    # lowercased action name -> last used; None when IAM has no action-level data for the service
    tracked: dict[str, datetime | None] | None = None


@dataclass
class AnalyzerEvidence:
    analyzer_arn: str | None = None
    unused_age_days: int | None = None
    role_unused: bool = False
    services: dict[str, set[str]] = field(default_factory=dict)  # ns -> unused actions (lower); empty = whole service
    error: str | None = None


@dataclass
class Evidence:
    role: dict
    policies: list[Policy]
    services: dict[str, ServiceUsage]
    report_completed: datetime | None
    analyzer: AnalyzerEvidence


def _doc(d) -> dict:
    if isinstance(d, str):
        return json.loads(urllib.parse.unquote(d))
    return d


def _code(e: Exception) -> str:
    resp = getattr(e, "response", None)
    if isinstance(resp, dict):
        return resp.get("Error", {}).get("Code") or type(e).__name__
    return type(e).__name__


def policies(iam, role_name: str) -> list[Policy]:
    out = []
    for page in iam.get_paginator("list_attached_role_policies").paginate(RoleName=role_name):
        for p in page.get("AttachedPolicies", []):
            arn = p["PolicyArn"]
            meta = iam.get_policy(PolicyArn=arn)["Policy"]
            ver = iam.get_policy_version(PolicyArn=arn, VersionId=meta["DefaultVersionId"])["PolicyVersion"]
            kind = "aws_managed" if arn.startswith("arn:aws:iam::aws:") or ":iam::aws:policy/" in arn else "customer_managed"
            out.append(Policy(p["PolicyName"], kind, _doc(ver["Document"]), arn, meta["DefaultVersionId"]))
    for page in iam.get_paginator("list_role_policies").paginate(RoleName=role_name):
        for name in page.get("PolicyNames", []):
            doc = iam.get_role_policy(RoleName=role_name, PolicyName=name)["PolicyDocument"]
            out.append(Policy(name, "inline", _doc(doc)))
    return out


def last_accessed(iam, role_arn: str, sleep=time.sleep, timeout_s: float = 120) -> tuple[dict, datetime | None]:
    job = iam.generate_service_last_accessed_details(Arn=role_arn, Granularity="ACTION_LEVEL")["JobId"]
    waited, delay = 0.0, 1.0
    while True:
        resp = iam.get_service_last_accessed_details(JobId=job)
        status = resp["JobStatus"]
        if status == "COMPLETED":
            break
        if status == "FAILED":
            raise RuntimeError(f"last-accessed job failed: {resp.get('Error', {}).get('Code', 'unknown')}")
        if waited >= timeout_s:
            raise TimeoutError("last-accessed job did not finish in time; re-run")
        sleep(delay)
        waited += delay
        delay = min(delay * 2, 10)
    services = {}
    for _ in range(MAX_PAGES):
        for s in resp.get("ServicesLastAccessed", []):
            tracked = None
            if "TrackedActionsLastAccessed" in s:
                tracked = {a["ActionName"].lower(): a.get("LastAccessedTime") for a in s["TrackedActionsLastAccessed"]}
            services[s["ServiceNamespace"].lower()] = ServiceUsage(
                s["ServiceNamespace"].lower(), s.get("ServiceName", s["ServiceNamespace"]), s.get("LastAuthenticated"),
                tracked)
        if not resp.get("IsTruncated"):
            break
        resp = iam.get_service_last_accessed_details(JobId=job, Marker=resp["Marker"])
    return services, resp.get("JobCompletionDate")


def analyzer_evidence(aa, role_arn: str, analyzer_arn: str | None = None) -> AnalyzerEvidence:
    """Access Analyzer unused-access findings for the role, if an unused-access analyzer exists.

    Missing analyzer or permissions is not an error: the IAM last-accessed report is enough.
    """
    ev = AnalyzerEvidence()
    try:
        if analyzer_arn is None:
            for t in ("ACCOUNT_UNUSED_ACCESS", "ORGANIZATION_UNUSED_ACCESS"):
                found = [a for a in aa.list_analyzers(type=t).get("analyzers", []) if a.get("status") == "ACTIVE"]
                if found:
                    analyzer_arn = found[0]["arn"]
                    age = found[0].get("configuration", {}).get("unusedAccess", {}).get("unusedAccessAge")
                    ev.unused_age_days = age
                    break
        if analyzer_arn is None:
            ev.error = "no active unused-access analyzer (it costs $0.20 per role per month; optional)"
            return ev
        ev.analyzer_arn = analyzer_arn
        params = {"analyzerArn": analyzer_arn, "filter": {
            "resource": {"eq": [role_arn]},
            "findingType": {"eq": ["UnusedPermission", "UnusedIAMRole"]},
            "status": {"eq": ["ACTIVE"]},
        }}
        ids = []
        for _ in range(MAX_PAGES):
            resp = aa.list_findings_v2(**params)
            ids += [(f["id"], f.get("findingType")) for f in resp.get("findings", [])]
            if not resp.get("nextToken"):
                break
            params["nextToken"] = resp["nextToken"]
        for fid, ftype in ids:
            if ftype == "UnusedIAMRole":
                ev.role_unused = True
                continue
            f = aa.get_finding_v2(analyzerArn=analyzer_arn, id=fid)
            for d in f.get("findingDetails", []):
                u = d.get("unusedPermissionDetails")
                if not u:
                    continue
                ns = u["serviceNamespace"].lower()
                # action may come as "s3:GetObject" or "GetObject"; keep the bare name
                ev.services.setdefault(ns, set()).update(
                    a["action"].lower().split(":", 1)[-1] for a in u.get("actions", []))
    except ReadOnlyViolation:
        raise
    except (ClientError, BotoCoreError) as e:
        ev.error = _code(e)
    return ev


def collect(iam, aa, role_name: str, analyzer_arn: str | None = None, sleep=time.sleep) -> Evidence:
    role = iam.get_role(RoleName=role_name)["Role"]
    pols = policies(iam, role_name)
    services, completed = last_accessed(iam, role["Arn"], sleep=sleep)
    analyzer = analyzer_evidence(aa, role["Arn"], analyzer_arn) if aa is not None else AnalyzerEvidence(error="skipped")
    return Evidence(role, pols, services, completed, analyzer)
