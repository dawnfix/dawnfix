"""Compute a least-privilege version of each policy from last-accessed evidence.

Conservative by design: an action is removed only when there is evidence it was not used.
- whole service not used within the window -> every action of that service goes
- explicit action that IAM tracks at action level and that was not used -> it goes
- wildcards inside a used service, NotAction, Deny, Action "*" -> kept untouched
  (a wildcard also covers actions IAM does not track, e.g. S3 object reads), with a
  narrowing suggestion when the used tracked actions are known
"""
from __future__ import annotations

import copy
import fnmatch
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .collect import Evidence, Policy

# Actions that are legitimately rare but break something important when missing.
# (pattern on lowercased "service:action", why)
RARE_BUT_CRITICAL = [
    ("*:restore*", "restore/DR path: typically only exercised during an incident or a drill"),
    ("rds:failover*", "failover: only used during an incident"),
    ("backup:start*", "backup/restore jobs: may run on a schedule longer than the window"),
    ("secretsmanager:rotatesecret", "secret rotation: runs every 30-90+ days"),
    ("secretsmanager:putsecretvalue", "rotation writes the new secret value"),
    ("acm:*", "certificate renewal and validation: often yearly"),
    ("route53:changeresourcerecordsets", "DNS changes: certificate validation and failover are rare but critical"),
    ("iam:passrole", "PassRole: used when infrastructure is created or redeployed, not in steady state"),
    ("cloudformation:*", "stack updates: only when infrastructure changes"),
    ("autoscaling:*", "scaling actions: may only fire under load"),
    ("application-autoscaling:*", "scaling actions: may only fire under load"),
    ("ssm:startsession", "break-glass shell access: only used during incidents"),
    ("ssm:sendcommand", "run-command: often only during incidents or patching"),
    ("sts:assumerole", "role chaining: break-glass or cross-account paths are rare"),
    ("kms:creategrant", "grants: created when volumes/instances or services attach keys"),
    ("ec2:createsnapshot*", "snapshots: may be on a weekly/monthly schedule"),
    ("lambda:updatefunctioncode", "deploy path: only when code ships"),
    ("ecs:registertaskdefinition", "deploy path: only when code ships"),
    ("ecs:updateservice", "deploy path: only when code ships"),
    ("elasticloadbalancing:registertargets", "deploy/scaling path"),
    ("elasticloadbalancing:deregistertargets", "deploy/scaling path"),
]
DESTRUCTIVE = ("delete", "terminate", "remove", "detach", "disable", "revoke", "deregister", "purge", "destroy")


@dataclass
class Removal:
    policy: str
    sid: str | None
    action: str
    basis: str  # service | action
    last_used: str | None
    sources: list[str]
    risk: str  # low | medium | high
    note: str


@dataclass
class PolicyChange:
    policy: Policy
    new_document: dict | None  # None: every statement went; detach/delete the policy
    removals: list[Removal] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.removals)


@dataclass
class TrimResult:
    role_name: str
    role_arn: str
    days: int
    evidence_days: int
    changes: list[PolicyChange]
    notes: list[str]

    @property
    def removals(self) -> list[Removal]:
        return [r for c in self.changes for r in c.removals]


def _list(v) -> list:
    return v if isinstance(v, list) else [v]


def _iso(d: datetime | None) -> str | None:
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).date().isoformat()


def _aware(d: datetime | None) -> datetime | None:
    if d is not None and d.tzinfo is None:
        return d.replace(tzinfo=timezone.utc)
    return d


def risk_for(action: str, basis: str, days: int, evidence_days: int, analyzer_agrees: bool) -> tuple[str, str]:
    a = action.lower()
    for pat, why in RARE_BUT_CRITICAL:
        if fnmatch.fnmatchcase(a, pat):
            note = f"{why}. Not seen in {evidence_days} days"
            if days < 365:
                note += "; a yearly or quarterly job would not show up in this window"
            return "high", note + ". Confirm with the owning team before merging."
    if evidence_days < days:
        return "medium", (f"role is only {evidence_days} days old, so the evidence covers {evidence_days} of the "
                          f"{days} days asked for")
    verb = a.split(":", 1)[-1]
    if basis == "service":
        note = f"the whole service was unused for {evidence_days}+ days"
    else:
        note = f"IAM tracks this action and saw no use in {evidence_days}+ days"
    if verb.startswith(DESTRUCTIVE):
        note += "; removing an unused destructive permission also shrinks the blast radius"
    if analyzer_agrees:
        note += "; Access Analyzer agrees"
    return "low", note + ". Re-add if something breaks."


def trim(ev: Evidence, days: int, now: datetime | None = None) -> TrimResult:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    created = _aware(ev.role.get("CreateDate"))
    evidence_days = days if created is None or created <= cutoff else max(0, (now - created).days)
    aa = ev.analyzer
    notes = []
    if created and created > cutoff:
        notes.append(f"Role was created {_iso(created)}: only {evidence_days} days of evidence.")
    if aa.error:
        notes.append(f"Access Analyzer unused-access findings not used: {aa.error}.")
    elif aa.unused_age_days and aa.unused_age_days != days:
        notes.append(f"Access Analyzer's unused-access window is {aa.unused_age_days} days, --days is {days}; "
                     "its agreement is reported but not required.")
    if aa.role_unused:
        notes.append("Access Analyzer reports the whole role as unused: consider deleting the role instead.")
    notes.append("IAM last-accessed data can lag by up to 4 hours and only covers authenticated calls this role made "
                 "itself.")

    def used(t: datetime | None) -> bool:
        t = _aware(t)
        return t is not None and t >= cutoff

    changes = []
    for pol in ev.policies:
        doc = copy.deepcopy(pol.document)
        change = PolicyChange(pol, doc)
        new_statements = []
        for st in _list(doc.get("Statement", [])):
            if st.get("Effect") != "Allow" or "Action" not in st:
                new_statements.append(st)
                continue
            keep = []
            for action in _list(st["Action"]):
                if action == "*" or ":" not in action:
                    keep.append(action)
                    continue
                ns, name = action.split(":", 1)
                ns, lname = ns.lower(), name.lower()
                svc = ev.services.get(ns)
                wildcard = "*" in name or "?" in name
                aa_actions = aa.services.get(ns)
                if svc is None:
                    keep.append(action)  # IAM did not report it: unknown service namespace; never guess
                    continue
                if not used(svc.last):
                    agrees = aa_actions is not None
                    sources = ["IAM last accessed"] + (["Access Analyzer"] if agrees else [])
                    lvl, note = risk_for(action, "service", days, evidence_days, agrees)
                    change.removals.append(Removal(pol.name, st.get("Sid"), action, "service", _iso(svc.last),
                                                   sources, lvl, note))
                    continue
                if svc.tracked is None:
                    keep.append(action)
                    continue
                if not wildcard:
                    if lname in svc.tracked and not used(svc.tracked[lname]):
                        agrees = aa_actions is not None and (not aa_actions or lname in aa_actions)
                        sources = ["IAM last accessed (action level)"] + (["Access Analyzer"] if agrees else [])
                        lvl, note = risk_for(action, "action", days, evidence_days, agrees)
                        change.removals.append(Removal(pol.name, st.get("Sid"), action, "action",
                                                       _iso(svc.tracked[lname]), sources, lvl, note))
                        continue
                    keep.append(action)
                    continue
                keep.append(action)
                hits = sorted(a for a, t in svc.tracked.items() if fnmatch.fnmatchcase(a, lname) and used(t))
                if hits:
                    change.suggestions.append(
                        f"`{action}` in {pol.name}: the tracked actions it was used for are "
                        f"{', '.join(f'{ns}:{h}' for h in hits)}. Not narrowed automatically: the wildcard also "
                        "covers actions IAM does not track.")
            if not keep:
                continue
            st = dict(st)
            st["Action"] = keep if isinstance(st["Action"], list) or len(keep) > 1 else keep[0]
            new_statements.append(st)
        if change.removals:
            change.new_document = {**doc, "Statement": new_statements} if new_statements else None
        else:
            change.new_document = pol.document
        changes.append(change)
    return TrimResult(ev.role.get("RoleName", ""), ev.role.get("Arn", ""), days, evidence_days, changes, notes)
