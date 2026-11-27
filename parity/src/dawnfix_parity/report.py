"""Render diff results and inventories as text, Markdown (job summary) or JSON.

Inputs carry names and metadata only; digests are never part of any rendered form.
"""
from __future__ import annotations

import json

from . import brand
from .diff import DiffResult
from .inventory import Row

LABEL = {
    "missing_in_left": "missing in {left}",
    "missing_in_right": "missing in {right}",
    "type_mismatch": "type mismatch",
    "dangling_reference": "reference to missing parameter/secret",
    "cross_env_reference": "references the other environment",
    "value_shared": "same value in both (hash)",
    "value_differs": "value differs (hash)",
    "unverifiable_reference": "reference not checkable",
    "duplicate_key": "names collide after normalisation",
    "plaintext_secret": "literal secret in a plain env var",
}


def _label(kind, res: DiffResult):
    return LABEL.get(kind, kind).format(left=res.left, right=res.right)


def diff_text(res: DiffResult, fail_on) -> str:
    lines = [f"{brand.PRODUCT_NAME}: {res.left} vs {res.right}"
             f" ({res.counts.get('keys_left', 0)} vs {res.counts.get('keys_right', 0)} keys,"
             f" {res.counts.get('references', 0)} references{', value hashes compared' if res.hashed else ''})"]
    active = res.active(fail_on)
    if not res.findings:
        lines.append("no drift")
    current = None
    for f in res.findings:
        head = "allowed" if f.allowed else _label(f.kind, res)
        if head != current:
            lines.append("")
            lines.append(f"{head}:")
            current = head
        sev = f"[{f.severity}]"
        extra = f"  ({f.allow_reason})" if f.allowed and f.allow_reason else ""
        lines.append(f"  {sev:9} {f.key}  {f.message}{extra}")
    if res.hashed:
        lines.append("")
        lines.append(f"values: {res.counts.get('values_equal', 0)} equal, {res.counts.get('values_differ', 0)} differ"
                     " (salted SHA-256, compared in memory; nothing printed or stored)")
    for w in res.warnings:
        lines.append(f"warning: {w}")
    lines.append("")
    lines.append(f"{len(active)} finding(s) fail the check" if active else "check: pass")
    return "\n".join(lines) + "\n"


def _md(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def diff_markdown(res: DiffResult, fail_on) -> str:
    active = res.active(fail_on)
    status = f"**{len(active)} finding(s) fail the check**" if active else "**pass**"
    out = [f"## {brand.PRODUCT_NAME}: `{res.left}` vs `{res.right}`", "",
           f"{status} · {res.counts.get('keys_left', 0)} keys in `{res.left}`, "
           f"{res.counts.get('keys_right', 0)} in `{res.right}`, {res.counts.get('references', 0)} references"
           + (" · value hashes compared" if res.hashed else ""), ""]
    if res.findings:
        out += ["| | Finding | Key | Detail |", "|---|---|---|---|"]
        for f in res.findings:
            mark = "allowed" if f.allowed else ("FAIL" if f in active else f.severity)
            detail = f.message + (f" ({f.allow_reason})" if f.allowed and f.allow_reason else "")
            out.append(f"| {mark} | {_md(_label(f.kind, res))} | `{_md(f.key)}` | {_md(detail)} |")
        out.append("")
    if res.hashed:
        out.append(f"Values: {res.counts.get('values_equal', 0)} equal, {res.counts.get('values_differ', 0)} differ "
                   "(salted SHA-256 in memory; values are never printed or stored).")
        out.append("")
    for w in res.warnings:
        out.append(f"> warning: {_md(w)}")
    out.append(f"<sub>{brand.PRODUCT_NAME} · read-only · names and metadata only</sub>")
    return "\n".join(out) + "\n"


def diff_json(res: DiffResult, fail_on) -> str:
    d = res.to_dict()
    d["fail_on"] = list(fail_on)
    d["failing"] = len(res.active(fail_on))
    return json.dumps(d, indent=2, default=str) + "\n"


def _date(v) -> str:
    if v is None:
        return "-"
    return str(v)[:10]


def inventory_text(rows_by_env: dict[str, list[Row]], cloudtrail_days: int | None) -> str:
    out = []
    for env, rows in rows_by_env.items():
        flagged = sum(1 for r in rows if r.flags)
        out.append(f"{env}: {len(rows)} secrets/parameters, {flagged} flagged"
                   + (f" (CloudTrail: last {cloudtrail_days} days)" if cloudtrail_days else ""))
        for r in rows:
            it = r.item
            rot = ("on" if it.meta.get("rotation_enabled") else "off") if it.kind == "secret" else "-"
            out.append(f"  {it.kind:6} {it.type:12} {it.name}")
            out.append(f"         changed {_date(it.meta.get('last_changed'))}  read {_date(r.last_read)}"
                       f"  rotation {rot} age {'-' if r.rotation_age_days is None else str(r.rotation_age_days) + 'd'}"
                       f"  refs {len(r.referenced_by)}")
            for ref in r.referenced_by:
                out.append(f"           <- {ref}")
            for p, n in sorted(r.readers.items(), key=lambda x: -x[1]):
                out.append(f"           read by {p} x{n}")
            if r.flags:
                out.append(f"         FLAGS: {', '.join(r.flags)}" + (f"  ({'; '.join(r.notes)})" if r.notes else ""))
        out.append("")
    return "\n".join(out)


def inventory_markdown(rows_by_env: dict[str, list[Row]], cloudtrail_days: int | None) -> str:
    out = [f"## {brand.PRODUCT_NAME}: inventory", ""]
    for env, rows in rows_by_env.items():
        out += [f"### `{env}`", "", "| Name | Type | Changed | Last read | Rotation | Referenced by | Flags |",
                "|---|---|---|---|---|---|---|"]
        for r in rows:
            it = r.item
            rot = ("on" if it.meta.get("rotation_enabled") else "off") if it.kind == "secret" else "-"
            out.append(f"| `{_md(it.name)}` | {it.type} | {_date(it.meta.get('last_changed'))} | {_date(r.last_read)} | "
                       f"{rot} | {len(r.referenced_by)} | {', '.join(r.flags) or '-'} |")
        out.append("")
    if cloudtrail_days:
        out.append(f"Readers from CloudTrail, last {cloudtrail_days} days.")
    return "\n".join(out) + "\n"


def inventory_json(rows_by_env: dict[str, list[Row]], cloudtrail_days: int | None) -> str:
    return json.dumps({"cloudtrail_days": cloudtrail_days,
                       "environments": {e: [r.to_dict() for r in rows] for e, rows in rows_by_env.items()}},
                      indent=2, default=str) + "\n"
