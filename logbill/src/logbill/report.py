"""The report: one self-contained HTML file (no external assets, light/dark, phone
width) and the same data as JSON."""
import json
from html import escape

from . import brand
from .prices import GB, usd

MAX_SUGGESTIONS = 15
MAX_GROUPS = 25
MAX_PATTERNS = 20

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1b18;--muted:#6b665e;--line:#e6e1d8;--card:#ffffff;--accent:#c8501e;
--accent-soft:#f6e3d8;--good:#2f7a4a;--good-soft:#e1f1e6;--code:#f3f0ea;--bar:#e8a57f}
@media (prefers-color-scheme:dark){:root{--bg:#141311;--fg:#ece8e1;--muted:#a39d93;--line:#2c2a26;
--card:#1c1b18;--accent:#f08a5a;--accent-soft:#3a2419;--good:#7fcf9b;--good-soft:#1b3123;--code:#24221e;--bar:#a5532c}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",
Roboto,"Helvetica Neue",Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:28px 16px 48px}
.eyebrow{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);font-weight:600}
h1{font-size:clamp(24px,5vw,34px);line-height:1.15;margin:6px 0 8px;letter-spacing:-.01em}
h1 .save{color:var(--good)}
h2{font-size:18px;margin:36px 0 10px}
.meta{color:var(--muted);font-size:13px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:22px 0 4px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kpi b{display:block;font-size:22px;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.kpi span{color:var(--muted);font-size:12px}
.kpi.good b{color:var(--good)}
@media (max-width:640px){.kpis{grid-template-columns:repeat(2,1fr)}}
ol.sugg{list-style:none;margin:0;padding:0;display:grid;gap:8px}
ol.sugg li{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;
display:grid;grid-template-columns:1fr auto;gap:2px 14px}
ol.sugg .amt{grid-row:1/span 3;grid-column:2;align-self:start;font-weight:700;color:var(--good);
background:var(--good-soft);border-radius:6px;padding:2px 8px;font-variant-numeric:tabular-nums;white-space:nowrap}
ol.sugg .t{font-weight:600}
ol.sugg .g,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px;overflow-wrap:anywhere}
ol.sugg .g{color:var(--muted)}
ol.sugg .d{font-size:13.5px;grid-column:1/span 2}
pre{background:var(--code);border-radius:6px;padding:8px 10px;margin:6px 0 0;font-size:12px;white-space:pre-wrap;
overflow-wrap:anywhere;grid-column:1/span 2}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600;white-space:nowrap}
tr:last-child td{border-bottom:0}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.name{min-width:180px;max-width:360px}
.bar{height:4px;border-radius:2px;background:var(--bar);margin-top:4px}
.chip{display:inline-block;font-size:11px;border-radius:999px;padding:1px 8px;margin:2px 4px 0 0;
background:var(--accent-soft);color:var(--accent);font-weight:600}
.warn{color:var(--accent);font-weight:600}
.empty{color:var(--muted);background:var(--card);border:1px dashed var(--line);border-radius:10px;padding:14px}
details{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
details summary{cursor:pointer;font-weight:600}
details ul{padding-left:18px;margin:8px 0 0;font-size:13.5px}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
footer b{color:var(--fg)}
"""

FLAG_LABEL = {"noisy": "noisy", "debug_in_prod": "DEBUG in prod", "lambda_platform": "Lambda platform"}
CLASS_LABEL = {"STANDARD": "Standard", "INFREQUENT_ACCESS": "Infrequent Access", "DELIVERY": "Delivery"}


def _e(x) -> str:
    return escape(str(x), quote=True)


def _gb(gb: float) -> str:
    if gb >= 100:
        return f"{gb:,.0f} GB"
    if gb >= 1:
        return f"{gb:,.1f} GB"
    return f"{gb * 1024:,.0f} MB"


def _retention(g: dict) -> str:
    if g["log_class"] == "DELIVERY":
        return "n/a"
    if g["retention_days"] is None:
        return '<span class="warn">never expires</span>'
    return f"{g['retention_days']} days"


def render_html(r: dict) -> str:
    t = r["totals"]
    groups = r["groups"]
    parts = []
    a = parts.append
    a("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">")
    a('<meta name="viewport" content="width=device-width,initial-scale=1">')
    a('<meta name="color-scheme" content="light dark">')
    a(f"<title>{_e(brand.SHORT)} report</title><style>{CSS}</style></head><body><main>")

    a(f'<div class="eyebrow">{_e(brand.PRODUCT)} &middot; CloudWatch Logs bill X-ray</div>')
    a(f"<h1>Your CloudWatch Logs bill is about {_e(usd(t['monthly_usd']))} a month."
      + (f' <span class="save">{_e(usd(t["savings_usd"]))} of it can go.</span>' if t["savings_usd"] >= 0.01 else "")
      + "</h1>")
    acct = f"Account {_e(r['account'])} &middot; " if r.get("account") else ""
    a(f'<div class="meta">{acct}{_e(", ".join(r["regions"]))} &middot; last {_e(r["days"])} days, '
      f"projected to 30 &middot; generated {_e(r['generated_at'][:16].replace('T', ' '))} UTC &middot; "
      f"{_e(t['free_tier_note'])}</div>")

    a('<div class="kpis">')
    a(f'<div class="kpi"><b>{_e(usd(t["monthly_usd"]))}</b><span>per month, {_e(t["groups"])} log groups</span></div>')
    a(f'<div class="kpi good"><b>{_e(usd(t["savings_usd"]))}</b><span>per month in savings found</span></div>')
    a(f'<div class="kpi"><b>{_e(_gb(t["monthly_ingest_gb"]))}</b><span>ingested per month '
      f'({_e(usd(t["ingest_usd"]))})</span></div>')
    a(f'<div class="kpi"><b>{_e(t["never_expire"])}</b><span>groups that never expire '
      f'({_e(_gb(t["stored_gb"]))} stored)</span></div>')
    a("</div>")

    # Suggestions
    a("<h2>Biggest savings</h2>")
    sugg = r["suggestions"][:MAX_SUGGESTIONS]
    if sugg:
        a('<ol class="sugg">')
        for s in sugg:
            a(f'<li><span class="t">{_e(s["title"])}</span><span class="amt">{_e(usd(s["monthly_usd"]))}/mo</span>'
              f'<span class="g">{_e(s["region"])} &middot; {_e(s["group"])}</span>'
              f'<span class="d">{_e(s["detail"])}</span>')
            if s.get("command"):
                a(f"<pre>{_e(s['command'])}</pre>")
            a("</li>")
        a("</ol>")
        if len(r["suggestions"]) > MAX_SUGGESTIONS:
            a(f'<p class="meta">{len(r["suggestions"]) - MAX_SUGGESTIONS} more in the JSON report.</p>')
        a('<p class="meta">Amounts overlap (retention at 30 and 90 days, dropping a line and moving its group to '
          'Infrequent Access); the headline total counts each dollar once.</p>')
    else:
        a('<p class="empty">Nothing worth changing was found.</p>')

    # Groups
    a("<h2>Costliest log groups</h2>")
    shown = [g for g in groups if g["monthly_usd"] > 0][:MAX_GROUPS]
    if shown:
        peak = max(g["monthly_usd"] for g in shown) or 1
        a('<div class="scroll"><table><thead><tr><th>Log group</th><th>Class</th><th>Retention</th>'
          '<th class="n">Ingested/mo</th><th class="n">Stored</th><th class="n">Filters</th><th class="n">$/mo</th>'
          "</tr></thead><tbody>")
        for g in shown:
            subs = "?" if g["subscription_filters"] is None else g["subscription_filters"]
            w = max(2, round(100 * g["monthly_usd"] / peak))
            a(f'<tr><td class="name"><div class="mono">{_e(g["name"])}</div>'
              f'<div class="meta">{_e(g["region"])}{" &middot; vended" if g["vended"] else ""}</div>'
              f'<div class="bar" style="width:{w}%"></div></td>'
              f"<td>{_e(CLASS_LABEL.get(g['log_class'], g['log_class']))}</td><td>{_retention(g)}</td>"
              f'<td class="n">{_e(_gb(g["monthly_ingest_gb"]))}</td>'
              f'<td class="n">{_e(_gb(g["stored_bytes"] / GB))}</td>'
              f'<td class="n" title="metric / subscription">{_e(g["metric_filters"])} / {_e(subs)}</td>'
              f'<td class="n"><b>{_e(usd(g["monthly_usd"]))}</b></td></tr>')
        a("</tbody></table></div>")
    else:
        a('<p class="empty">No log group cost anything in this window.</p>')

    # Patterns
    a("<h2>Costliest log lines</h2>")
    pats = []
    for g in groups:
        for p in g.get("patterns", []):
            pats.append((p, g))
    pats.sort(key=lambda x: x[0]["monthly_usd"], reverse=True)
    if pats:
        a('<div class="scroll"><table><thead><tr><th>Pattern (redacted)</th><th class="n">Share</th>'
          '<th class="n">$/mo</th></tr></thead><tbody>')
        for p, g in pats[:MAX_PATTERNS]:
            chips = "".join(f'<span class="chip">{_e(FLAG_LABEL.get(f, f))}</span>' for f in p.get("flags", []))
            a(f'<tr><td class="name"><div class="mono">{_e(p["text"])}</div>'
              f'<div class="meta">{_e(g["name"])} &middot; id {_e(p["id"])}</div>{chips}</td>'
              f'<td class="n">{p["byte_share"]:.0%}</td><td class="n"><b>{_e(usd(p["monthly_usd"]))}</b></td></tr>')
        a("</tbody></table></div>")
        a(f'<p class="meta">Map these to source lines: <span class="mono">{_e(brand.CLI)} locate --repo PATH '
          f"--report &lt;this report&gt;.json</span></p>")
    else:
        a('<p class="empty">No pattern analysis in this report (Logs Insights did not run).</p>')

    # Insights
    ins = r["insights"]
    a("<h2>What this report cost</h2>")
    if ins.get("ran"):
        a(f"<p>Logs Insights scanned {_e(_gb(ins['scanned_gb']))} for about {_e(usd(ins['usd']))} "
          f"(budget {_e(ins['budget_gb'])} GB, planned {_e(_gb(ins['planned_gb']))}). "
          "Everything else was metadata and metrics.</p>")
    else:
        a(f"<p>No Logs Insights query ran (budget {_e(ins['budget_gb'])} GB). The scan read metadata and "
          "CloudWatch metrics only.</p>")

    # Method
    src = r.get("prices_source", {})
    a("<h2>How the numbers were made</h2><details><summary>Prices, assumptions and notes</summary><ul>")
    a(f"<li>Prices: AWS Price List for CloudWatch, published {_e(src.get('publication_date', '?'))}, "
      f"read {_e(src.get('retrieved', '?'))}. Edit <span class=\"mono\">prices.json</span> to change them.</li>")
    a(f"<li>Ingestion: AWS/Logs IncomingBytes per log group over {_e(r['days'])} days, scaled to 30.</li>")
    a("<li>Storage: storedBytes from DescribeLogGroups at the region's GB-month rate. Retention savings assume "
      "the stored bytes built up evenly since the group was created.</li>")
    a("<li>Per-line cost: Logs Insights <span class=\"mono\">pattern</span> counts over a short window, weighted by "
      "line length, applied to the group's monthly ingestion cost.</li>")
    a("<li>Vended logs (Lambda, /aws/vendedlogs/) are priced on the region's volume tiers.</li>")
    for n in r.get("notes", []):
        a(f"<li>{_e(n)}</li>")
    for e in r.get("errors", []):
        a(f'<li class="warn">{_e(e["region"])}: {_e(e["code"])}</li>')
    a("</ul></details>")

    a(f"<footer><p><b>{_e(brand.PITCH_PRODUCT)}</b>: {_e(brand.PITCH_LINE)} {_e(brand.PITCH_TEXT)}</p>"
      f"<p>Made on your machine with your own AWS credentials. Nothing was uploaded. "
      f"{_e(brand.PRODUCT)}. {_e(brand.LICENCE)}.</p></footer>")
    a("</main></body></html>")
    return "".join(parts)


def render_json(r: dict) -> str:
    return json.dumps(r, indent=2, default=str) + "\n"


def summary_text(r: dict, html_path: str | None, json_path: str | None) -> str:
    t = r["totals"]
    lines = [f"{brand.PRODUCT}: about {usd(t['monthly_usd'])}/month across {t['groups']} log groups "
             f"({', '.join(r['regions'])}); savings found: {usd(t['savings_usd'])}/month."]
    for s in r["suggestions"][:5]:
        lines.append(f"  {usd(s['monthly_usd']):>9}/mo  {s['title']}  [{s['region']} {s['group']}]")
    ins = r["insights"]
    if ins.get("ran"):
        lines.append(f"Logs Insights scanned {ins['scanned_gb']:.2f} GB (~{usd(ins['usd'])}).")
    for n in r.get("notes", []):
        lines.append(f"note: {n}")
    if html_path:
        lines.append(f"report: {html_path}")
    if json_path:
        lines.append(f"json: {json_path}")
    return "\n".join(lines)
