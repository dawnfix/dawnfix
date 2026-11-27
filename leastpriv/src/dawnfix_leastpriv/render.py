"""Turn a TrimResult into PR-ready files: JSON / Terraform / CloudFormation diffs and a PR body."""
from __future__ import annotations

import difflib
import json
import re

from . import __version__
from .constants import BRAND, HOMEPAGE, PITCH_LINE, PITCH_URL
from .trim import PolicyChange, TrimResult

FORMATS = ("json", "terraform", "cloudformation")


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", s).strip("_").lower() or "policy"


def as_json(doc: dict | None) -> str:
    return "" if doc is None else json.dumps(doc, indent=2) + "\n"


# --- Terraform: aws_iam_policy_document -----------------------------------------------

def _hcl_str(s) -> str:
    return json.dumps(str(s)).replace("${", "$${")


def _hcl_list(v) -> str:
    items = v if isinstance(v, list) else [v]
    if len(items) <= 1:
        return "[" + ", ".join(_hcl_str(i) for i in items) + "]"
    return "[\n" + "".join(f"      {_hcl_str(i)},\n" for i in items) + "    ]"


def as_terraform(doc: dict | None, name: str) -> str:
    if doc is None:
        return f'# {name}: every statement was removed; delete this policy document and its attachment.\n'
    lines = [f'data "aws_iam_policy_document" "{_slug(name)}" {{']
    for st in doc.get("Statement", []) if isinstance(doc.get("Statement"), list) else [doc["Statement"]]:
        lines.append("  statement {")
        if st.get("Sid"):
            lines.append(f"    sid       = {_hcl_str(st['Sid'])}")
        lines.append(f"    effect    = {_hcl_str(st.get('Effect', 'Allow'))}")
        for key, tf in (("Action", "actions"), ("NotAction", "not_actions"), ("Resource", "resources"),
                        ("NotResource", "not_resources")):
            if key in st:
                lines.append(f"    {tf:<9} = {_hcl_list(st[key])}")
        for test, conds in (st.get("Condition") or {}).items():
            for var, values in conds.items():
                lines += ["    condition {", f"      test     = {_hcl_str(test)}",
                          f"      variable = {_hcl_str(var)}",
                          f"      values   = [{', '.join(_hcl_str(v) for v in (values if isinstance(values, list) else [values]))}]",
                          "    }"]
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"


# --- CloudFormation: YAML PolicyDocument --------------------------------------------------

def _yaml_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(str(v))  # double-quoted JSON strings are valid YAML


def _yaml(v, indent: int) -> list[str]:
    pad = " " * indent
    if isinstance(v, dict):
        out = []
        for k, x in v.items():
            k = k if re.fullmatch(r"[A-Za-z0-9_]+", k) else json.dumps(k)
            if isinstance(x, (dict, list)) and x:
                out.append(f"{pad}{k}:")
                out += _yaml(x, indent + 2)
            else:
                out.append(f"{pad}{k}: {_yaml_scalar(x) if not isinstance(x, (dict, list)) else ('{}' if isinstance(x, dict) else '[]')}")
        return out
    if isinstance(v, list):
        out = []
        for x in v:
            sub = _yaml(x, indent + 2)
            out.append(f"{pad}- {sub[0].lstrip()}")
            out += sub[1:]
        return out
    return [f"{pad}{_yaml_scalar(v)}"]


def as_cloudformation(doc: dict | None, name: str) -> str:
    if doc is None:
        return f"# {name}: every statement was removed; delete this policy from the template.\n"
    return "\n".join([f"# {name}", "PolicyDocument:"] + _yaml(doc, 2)) + "\n"


# --- diffs ----------------------------------------------------------------------------------

def render(fmt: str, doc: dict | None, name: str) -> str:
    return {"json": lambda: as_json(doc), "terraform": lambda: as_terraform(doc, name),
            "cloudformation": lambda: as_cloudformation(doc, name)}[fmt]()


def diff(change: PolicyChange, fmt: str, path: str | None = None) -> str:
    name = change.policy.name
    ext = {"json": "json", "terraform": "tf", "cloudformation": "yaml"}[fmt]
    path = path or f"iam/{_slug(name)}.{ext}"
    old = render(fmt, change.policy.document, name).splitlines(keepends=True)
    new = render(fmt, change.new_document, name).splitlines(keepends=True)
    return "".join(difflib.unified_diff(old, new, f"a/{path}", f"b/{path}"))


def pr_body(r: TrimResult, formats=FORMATS) -> str:
    rem = r.removals
    by_risk = {k: sum(1 for x in rem if x.risk == k) for k in ("high", "medium", "low")}
    out = [f"## Least privilege for `{r.role_name}`", "",
           f"Removes {len(rem)} permission(s) not used in the last {r.days} days "
           f"({by_risk['high']} high, {by_risk['medium']} medium, {by_risk['low']} low risk). "
           f"Generated read-only by {BRAND} {__version__}; nothing was applied to AWS.", ""]
    if r.notes:
        out += ["**Evidence notes**", ""] + [f"- {n}" for n in r.notes] + [""]
    for c in r.changes:
        if not c.changed:
            continue
        pol = c.policy
        where = {"inline": "inline policy", "customer_managed": f"customer managed `{pol.arn}`",
                 "aws_managed": f"AWS managed `{pol.arn}`"}[pol.kind]
        out += [f"### {pol.name} ({where})", ""]
        if pol.kind == "aws_managed":
            out += ["AWS managed policies cannot be edited. Detach it and attach a customer managed policy with "
                    "the document below instead.", ""]
        if c.new_document is None:
            out += ["Every statement was removed: detach and delete this policy.", ""]
        out += ["| Risk | Action | Why it goes | Last used | Evidence |", "|---|---|---|---|---|"]
        order = {"high": 0, "medium": 1, "low": 2}
        for x in sorted(c.removals, key=lambda x: (order[x.risk], x.action)):
            out.append(f"| {x.risk} | `{x.action}` | {x.note} | {x.last_used or 'never'} | "
                       f"{' + '.join(x.sources)} |")
        out.append("")
        for s in c.suggestions:
            out.append(f"- Suggestion: {s}")
        if c.suggestions:
            out.append("")
        for fmt in formats:
            lang = {"json": "diff", "terraform": "diff", "cloudformation": "diff"}[fmt]
            out += [f"<details><summary>{fmt} diff</summary>", "", f"```{lang}", diff(c, fmt).rstrip("\n"), "```",
                    "", "</details>", ""]
    if not rem:
        out += ["Nothing to remove: every granted service was used in the window, and no tracked explicit action "
                "went unused.", ""]
        for c in r.changes:
            out += [f"- Suggestion: {s}" for s in c.suggestions]
    out += ["", f"<sub>Merge only after the high-risk rows are confirmed. {HOMEPAGE}</sub>", ""]
    return "\n".join(out)


def report(r: TrimResult) -> dict:
    return {
        "version": __version__, "role": r.role_name, "role_arn": r.role_arn, "days": r.days,
        "evidence_days": r.evidence_days, "applied": False, "notes": r.notes,
        "policies": [{
            "name": c.policy.name, "kind": c.policy.kind, "arn": c.policy.arn, "changed": c.changed,
            "delete_policy": c.changed and c.new_document is None,
            "new_document": c.new_document if c.changed else None,
            "removals": [x.__dict__ for x in c.removals], "suggestions": c.suggestions,
        } for c in r.changes],
        "pitch": {"line": PITCH_LINE, "url": PITCH_URL},
    }
