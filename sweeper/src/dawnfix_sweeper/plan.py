"""Render a scan into a teardown plan: JSON for machines, Markdown for the humans who run it."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from . import __version__
from .constants import BRAND, HOMEPAGE, LICENCE, TOOL, pitch
from .scan import KIND_TITLES, PHASES, Item


def _usd(v: float | None) -> str:
    return "n/a" if v is None else f"${v:,.2f}"


def build(result: dict, *, before: datetime, regions: list[str], tags: dict, prices_meta: dict,
          now: datetime | None = None) -> dict:
    items: list[Item] = result["items"]
    now = now or datetime.now(timezone.utc)

    def total(action=None):
        return round(sum(i.monthly_usd or 0 for i in items if action is None or i.action == action), 2)

    return {
        "tool": TOOL,
        "version": __version__,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "account": result.get("account"),
        "regions": regions,
        "before_date": before.date().isoformat(),
        "tag_filter": tags,
        "executed": False,
        "price_table": prices_meta,
        "summary": {
            "items": len(items),
            "delete": sum(1 for i in items if i.action == "delete"),
            "verify": sum(1 for i in items if i.action == "verify"),
            "monthly_usd_total": total(),
            "monthly_usd_delete": total("delete"),
            "monthly_usd_verify": total("verify"),
            "by_kind": {k: sum(1 for i in items if i.kind == k) for k in PHASES if any(i.kind == k for i in items)},
        },
        "items": [i.to_dict() for i in items],
        "errors": result.get("errors", []),
        "notes": result.get("notes", []),
        "pitch": pitch(total()),
    }


_CTRL = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")


def _cell(v: object) -> str:
    """AWS names, tags and descriptions are untrusted (anyone who can tag a resource
    writes them): keep them on one line and unable to break the table or code spans."""
    t = _CTRL.sub(" ", str(v)).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = t.replace("`", "'")
    # Backslash-escape every Markdown inline metacharacter (links, images, emphasis, headings).
    return re.sub(r"([\\|\[\]()!*_~#])", r"\\\1", t)


_FENCE = re.compile(r"^\s*(```|~~~)", re.M)


def _command(cmd: str) -> str:
    """A command line for the bash block. Commands are shell-quoted already, but a quoted
    value with a newline would span lines (and could close the fence), so refuse those."""
    if _CTRL.search(cmd) or _FENCE.search(cmd):
        return "# SKIPPED: this command contains a line break or control character from a resource name; run it by hand using the resource id"
    return cmd


def _comment(v: object) -> str:
    """Text placed after `#` inside the bash block: never a newline, so it can't start a command."""
    return _CTRL.sub(" ", str(v))


def markdown(plan: dict) -> str:
    s = plan["summary"]
    tag_txt = _cell(", ".join(f"{k}={v}" if v is not None else k for k, v in plan["tag_filter"].items()) or "none")
    out = [
        f"# Teardown plan: {_cell(plan['account'] or 'unknown account')}, cutover {_cell(plan['before_date'])}",
        "",
        f"Generated {plan['generated_at']} by {BRAND} {plan['version']} (read-only). "
        "**Nothing was deleted.** Every command below is for a human to review and run.",
        "",
        f"- Regions: {_cell(', '.join(plan['regions']))} · tag filter: {tag_txt}",
        f"- {s['items']} items: {s['delete']} safe to delete, {s['verify']} to verify first",
        f"- Estimated waste: **{_usd(s['monthly_usd_total'])}/month** "
        f"({_usd(s['monthly_usd_delete'])} delete, {_usd(s['monthly_usd_verify'])} verify)",
        f"- Prices: AWS on-demand list prices for {_cell(', '.join(plan['regions']))} (AWS Price List, newest offer "
        f"published {_cell(plan['price_table']['as_of'])}); estimates, not a bill.",
        "",
    ]
    if plan["errors"]:
        out += ["## Not scanned", "", "| Collector | Region | Error |", "|---|---|---|"]
        out += [f"| {_cell(e['collector'])} | {_cell(e['region'])} | {_cell(e['error_code'])} |" for e in plan["errors"]]
        out.append("")
    by_kind: dict[str, list[dict]] = {}
    for it in plan["items"]:
        by_kind.setdefault(it["kind"], []).append(it)
    for kind in sorted(by_kind, key=PHASES.get):
        rows = by_kind[kind]
        out += [f"## {PHASES[kind]}. {KIND_TITLES[kind]}", "",
                "| | Name | Region | Why | $/month | Basis |", "|---|---|---|---|---:|---|"]
        for it in rows:
            flag = "delete" if it["action"] == "delete" else "**verify**"
            name = _cell(it["name"]) if it["name"] == it["id"] else f"{_cell(it['name'])} `{_cell(it['id'])}`"
            out.append(f"| {flag} | {name} | {_cell(it['region'])} | {_cell(it['reason'])} | {_usd(it['monthly_usd'])} "
                       f"| {_cell(it['cost_note'])} |")
        out.append("")
    if plan["items"]:
        out += ["## Commands (in this order)", "",
                "Run top to bottom. Lines marked `# VERIFY` need a human check first. "
                "Optional backups are commented out.", "", "```bash"]
        phase = None
        for it in plan["items"]:
            if it["phase"] != phase:
                phase = it["phase"]
                out.append(f"\n# --- {phase}. {_comment(KIND_TITLES[it['kind']])}")
            if it["action"] == "verify":
                out.append(f"# VERIFY: {_comment(it['reason'])}")
            for b in it["backup_commands"]:
                out.append(f"# backup: {_comment(b)}")
            out += [_command(c) for c in it["commands"]]
        out += ["```", ""]
    else:
        out += ["Nothing left behind matched. Clean cutover.", ""]
    if plan["notes"]:
        out += ["## Notes", ""] + [f"- {_cell(n)}" for n in plan["notes"]] + [""]
    out += ["## Price sources", ""] + [f"- {_cell(u)}" for u in plan["price_table"]["sources"]]
    out += ["", f"_{_cell(plan['price_table']['note'])}_", "", f"{BRAND} · {LICENCE} · {HOMEPAGE}", ""]
    return "\n".join(out)
